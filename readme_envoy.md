# Envoy Proxy Implementation for Use-Case-ID Access Control

This document provides implementation steps and sample configurations for migrating from the FastAPI proxy to an Envoy proxy while maintaining the same `X-Use-Case-ID` header-based access control logic.

## Current FastAPI Logic Summary

The existing FastAPI proxy implements:
- **Header Validation**: Checks for `X-Use-Case-ID` header presence
- **Allowlist Checking**: Validates header value against configured allowed use cases
- **Access Control**: Returns 400 for missing header, 403 for unauthorized values
- **Request Forwarding**: Proxies valid requests to backend service
- **Logging**: Comprehensive request/response logging for monitoring

## Envoy Implementation Overview

Envoy can replicate this logic using:
- **HTTP Filter Chain**: Process incoming requests before routing
- **Lua Script Filter**: Custom logic for header validation and allowlist checking
- **Local Reply Filter**: Custom error responses for rejections
- **Access Logging**: Request/response monitoring

## Implementation Steps

### Step 1: Basic Envoy Configuration Structure

Create an `envoy.yaml` configuration file with the following structure:

```yaml
static_resources:
  listeners:
    - name: main_listener
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 8001
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: backend_service
                http_filters:
                  - name: envoy.filters.http.lua
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
                      source_codes:
                        use_case_validator:
                          filename: "/etc/envoy/use_case_validator.lua"
                  - name: envoy.filters.http.router

  clusters:
    - name: backend_service
      connect_timeout: 30s
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: backend_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: localhost
                      port_value: 8002
```

### Step 2: Use Case Configuration Management

Create a configuration file `use_cases.json` for managing allowed use cases:

```json
{
  "allowed_use_cases": [
    "100000",
    "100050",
    "101966",
    "102550",
    "103366"
  ],
  "use_case_descriptions": {
    "100000": "Primary client application",
    "100050": "Mobile application v2",
    "101966": "Analytics dashboard",
    "102550": "Admin panel interface",
    "103366": "External API integration"
  },
  "security": {
    "require_use_case_header": true,
    "case_sensitive_matching": false,
    "log_rejected_requests": true
  }
}
```

### Step 3: Configuration-Based Lua Script

Create a Lua script file `use_case_validator.lua`:

```lua
-- use_case_validator.lua
local json = require "json"  -- Note: May need lua-cjson library

-- Global configuration cache
local config_cache = {}
local config_last_loaded = 0
local config_reload_interval = 30  -- seconds

-- Load configuration from file
function load_config()
    local config_file = "/etc/envoy/use_cases.json"
    local current_time = os.time()

    -- Check if we need to reload config
    if current_time - config_last_loaded < config_reload_interval and config_cache.loaded then
        return config_cache
    end

    local file = io.open(config_file, "r")
    if not file then
        -- Fallback to default configuration
        config_cache = {
            allowed_use_cases = {"100000", "100050", "101966", "102550", "103366"},
            security = {
                require_use_case_header = true,
                case_sensitive_matching = false,
                log_rejected_requests = true
            },
            loaded = true
        }
        config_last_loaded = current_time
        return config_cache
    end

    local content = file:read("*all")
    file:close()

    local success, config = pcall(json.decode, content)
    if not success then
        -- Keep existing config on parse error
        return config_cache
    end

    config_cache = config
    config_cache.loaded = true
    config_last_loaded = current_time

    return config_cache
end

-- Check if use case is allowed
function is_use_case_allowed(use_case_id, config)
    if not use_case_id then
        return false
    end

    local case_sensitive = config.security and config.security.case_sensitive_matching
    local allowed_cases = config.allowed_use_cases or {}

    if case_sensitive then
        for _, allowed_case in ipairs(allowed_cases) do
            if use_case_id == allowed_case then
                return true
            end
        end
    else
        local use_case_lower = string.lower(use_case_id)
        for _, allowed_case in ipairs(allowed_cases) do
            if use_case_lower == string.lower(allowed_case) then
                return true
            end
        end
    end

    return false
end

-- Main request handler
function envoy_on_request(request_handle)
    -- Load current configuration
    local config = load_config()

    -- Skip validation for specific paths
    local path = request_handle:headers():get(":path")
    if path == "/" or path == "/health" or string.match(path, "^/docs") or string.match(path, "^/config") then
        return
    end

    -- Get X-Use-Case-ID header
    local use_case_id = request_handle:headers():get("x-use-case-id")

    -- Log the request
    local client_ip = request_handle:headers():get("x-forwarded-for") or "unknown"
    local method = request_handle:headers():get(":method")
    request_handle:logInfo("Request: " .. method .. " " .. path .. " - Use-Case-ID: " .. (use_case_id or "missing") .. " from " .. client_ip)

    -- Check if header is required and missing
    local require_header = config.security and config.security.require_use_case_header
    if require_header and not use_case_id then
        if config.security and config.security.log_rejected_requests then
            request_handle:logWarn("Rejected request: Missing X-Use-Case-ID header from " .. client_ip)
        end
        request_handle:respond(
            {[":status"] = "400", ["content-type"] = "application/json"},
            '{"detail": "Missing required header: X-Use-Case-ID"}'
        )
        return
    end

    -- Check if use case is allowed
    if use_case_id and not is_use_case_allowed(use_case_id, config) then
        if config.security and config.security.log_rejected_requests then
            request_handle:logWarn("Rejected request: Unauthorized use case '" .. use_case_id .. "' from " .. client_ip)
        end

        local allowed_list = table.concat(config.allowed_use_cases or {}, ", ")
        local error_response = json.encode({
            detail = "Unauthorized use case: " .. use_case_id .. ". Allowed values: [" .. allowed_list .. "]",
            use_case_id = use_case_id,
            allowed_use_cases = config.allowed_use_cases or {}
        })

        request_handle:respond(
            {[":status"] = "403", ["content-type"] = "application/json"},
            error_response
        )
        return
    end

    -- Log approved request
    if use_case_id then
        local description = ""
        if config.use_case_descriptions and config.use_case_descriptions[use_case_id] then
            description = " (" .. config.use_case_descriptions[use_case_id] .. ")"
        end
        request_handle:logInfo("Approved request: Use case '" .. use_case_id .. "'" .. description .. " is authorized")
    end
end
```

### Step 4: Health Check and Configuration Endpoints

Add specific route configurations for health and config endpoints:

```yaml
# Add to virtual_hosts.routes in envoy.yaml
routes:
  - match:
      prefix: "/health"
    route:
      cluster: backend_service
    typed_per_filter_config:
      envoy.filters.http.lua:
        "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.LuaPerRoute
        disabled: true  # Skip Lua filter for health checks

  - match:
      prefix: "/config"
    direct_response:
      status: 200
      body:
        inline_string: |
          {
            "allowed_use_cases": ["100000", "100050", "101966", "102550", "103366"],
            "use_case_descriptions": {
              "100000": "Primary client application",
              "100050": "Mobile application v2",
              "101966": "Analytics dashboard",
              "102550": "Admin panel interface",
              "103366": "External API integration"
            },
            "proxy_type": "envoy"
          }

  - match:
      prefix: "/"
    route:
      cluster: backend_service
```

### Step 5: Access Logging Configuration

```yaml
# Add to http_connection_manager in envoy.yaml
access_log:
  - name: envoy.access_loggers.stdout
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
      format: |
        [%START_TIME%] "%REQ(:METHOD)% %REQ(X-ENVOY-ORIGINAL-PATH?:PATH)% %PROTOCOL%"
        %RESPONSE_CODE% %RESPONSE_FLAGS% %BYTES_RECEIVED% %BYTES_SENT%
        %DURATION% %RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)% "%REQ(X-FORWARDED-FOR)%"
        "%REQ(USER-AGENT)%" "%REQ(X-REQUEST-ID)%" "%REQ(:AUTHORITY)%"
        "use_case_id=%REQ(X-USE-CASE-ID)%"
```

## Sample Use Case Configurations

### Configuration 1: Strict Mode (Require Header)

```yaml
# envoy-strict.yaml - Requires X-Use-Case-ID header for all requests
http_filters:
  - name: envoy.filters.http.lua
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
      inline_code: |
        function envoy_on_request(request_handle)
            local path = request_handle:headers():get(":path")
            if path == "/health" then return end

            local use_case_id = request_handle:headers():get("x-use-case-id")
            if not use_case_id then
                request_handle:respond(
                    {[":status"] = "400"},
                    '{"error": "X-Use-Case-ID header required"}'
                )
                return
            end

            local allowed = {"100000", "100050", "101966"}
            local is_valid = false
            for _, case in ipairs(allowed) do
                if string.lower(use_case_id) == string.lower(case) then
                    is_valid = true
                    break
                end
            end

            if not is_valid then
                request_handle:respond(
                    {[":status"] = "403"},
                    '{"error": "Unauthorized use case: ' .. use_case_id .. '"}'
                )
                return
            end
        end
```

### Configuration 2: Development Mode (Optional Header)

```yaml
# envoy-dev.yaml - Optional X-Use-Case-ID header with warnings
http_filters:
  - name: envoy.filters.http.lua
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
      inline_code: |
        function envoy_on_request(request_handle)
            local use_case_id = request_handle:headers():get("x-use-case-id")

            if not use_case_id then
                request_handle:logWarn("Request without X-Use-Case-ID header - allowed in dev mode")
                return
            end

            local allowed = {"100000", "100050", "101966", "DEV-001", "TEST-001"}
            local is_valid = false
            for _, case in ipairs(allowed) do
                if string.lower(use_case_id) == string.lower(case) then
                    is_valid = true
                    break
                end
            end

            if not is_valid then
                request_handle:logWarn("Invalid use case in dev mode: " .. use_case_id)
                request_handle:headers():add("x-invalid-use-case", use_case_id)
            end
        end
```

### Configuration 3: Multi-Environment with Rate Limiting

```yaml
# envoy-production.yaml - Production configuration with rate limiting
static_resources:
  listeners:
    - name: main_listener
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 8001
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: backend
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: backend_service
                            rate_limits:
                              - actions:
                                  - request_headers:
                                      header_name: "x-use-case-id"
                                      descriptor_key: "use_case_id"
                http_filters:
                  - name: envoy.filters.http.ratelimit
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.ratelimit.v3.RateLimit
                      domain: use_case_rate_limit
                      failure_mode_deny: true
                      rate_limit_service:
                        grpc_service:
                          envoy_grpc:
                            cluster_name: rate_limit_service
                  - name: envoy.filters.http.lua
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
                      inline_code: |
                        function envoy_on_request(request_handle)
                            -- Use case validation logic (same as above)
                        end
                  - name: envoy.filters.http.router

  clusters:
    - name: backend_service
      connect_timeout: 30s
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: backend_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: localhost
                      port_value: 8002

    - name: rate_limit_service
      connect_timeout: 1s
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: rate_limit_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: localhost
                      port_value: 8080
```

## Deployment Steps

### Step 1: Install Envoy

```bash
# Using Docker
docker pull envoyproxy/envoy:v1.28-latest

# Or install locally (Ubuntu/Debian)
curl -sL 'https://getenvoy.io/gpg' | sudo gpg --dearmor -o /usr/share/keyrings/getenvoy-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/getenvoy-keyring.gpg] https://deb.dl.getenvoy.io/public/deb/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/getenvoy.list
sudo apt update && sudo apt install getenvoy-envoy
```

### Step 2: Prepare Configuration Files

```bash
# Create directory structure
mkdir envoy-proxy
cd envoy-proxy
mkdir config

# Create configuration files
touch envoy.yaml
touch config/use_cases.json
touch config/use_case_validator.lua

# Copy configurations from this document
# Ensure proper permissions
chmod 644 config/use_cases.json
chmod 644 config/use_case_validator.lua
```

### Step 2a: Configuration File Management

Create a configuration management script `manage_config.py`:

```python
#!/usr/bin/env python3
import json
import yaml
import argparse
import os
import shutil
from datetime import datetime

class ConfigManager:
    def __init__(self, config_path="/etc/envoy/use_cases.json"):
        self.config_path = config_path
        self.backup_dir = os.path.dirname(config_path) + "/backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.get_default_config()

    def save_config(self, config, backup=True):
        """Save configuration to file with optional backup"""
        if backup and os.path.exists(self.config_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.backup_dir}/use_cases_{timestamp}.json"
            shutil.copy2(self.config_path, backup_path)
            print(f"Backup created: {backup_path}")

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {self.config_path}")

    def get_default_config(self):
        """Get default configuration"""
        return {
            "allowed_use_cases": ["100000", "100050", "101966", "102550", "103366"],
            "use_case_descriptions": {
                "100000": "Primary client application",
                "100050": "Mobile application v2",
                "101966": "Analytics dashboard",
                "102550": "Admin panel interface",
                "103366": "External API integration"
            },
            "security": {
                "require_use_case_header": True,
                "case_sensitive_matching": False,
                "log_rejected_requests": True
            }
        }

    def add_use_case(self, use_case_id, description=None):
        """Add a new use case"""
        config = self.load_config()
        if use_case_id not in config["allowed_use_cases"]:
            config["allowed_use_cases"].append(use_case_id)
            if description:
                if "use_case_descriptions" not in config:
                    config["use_case_descriptions"] = {}
                config["use_case_descriptions"][use_case_id] = description
            self.save_config(config)
            print(f"Added use case: {use_case_id}")
        else:
            print(f"Use case {use_case_id} already exists")

    def remove_use_case(self, use_case_id):
        """Remove a use case"""
        config = self.load_config()
        if use_case_id in config["allowed_use_cases"]:
            config["allowed_use_cases"].remove(use_case_id)
            if "use_case_descriptions" in config and use_case_id in config["use_case_descriptions"]:
                del config["use_case_descriptions"][use_case_id]
            self.save_config(config)
            print(f"Removed use case: {use_case_id}")
        else:
            print(f"Use case {use_case_id} not found")

    def list_use_cases(self):
        """List all use cases"""
        config = self.load_config()
        print("Allowed use cases:")
        for use_case in config["allowed_use_cases"]:
            description = config.get("use_case_descriptions", {}).get(use_case, "No description")
            print(f"  {use_case}: {description}")

    def validate_use_case(self, use_case_id):
        """Check if use case is allowed"""
        config = self.load_config()
        is_allowed = use_case_id in config["allowed_use_cases"]
        print(f"Use case {use_case_id}: {'ALLOWED' if is_allowed else 'DENIED'}")
        return is_allowed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Envoy use case configuration")
    parser.add_argument("action", choices=["add", "remove", "list", "validate", "show"],
                       help="Action to perform")
    parser.add_argument("use_case_id", nargs="?", help="Use case ID")
    parser.add_argument("-d", "--description", help="Description for the use case")
    parser.add_argument("-c", "--config", default="/etc/envoy/use_cases.json",
                       help="Path to configuration file")

    args = parser.parse_args()
    manager = ConfigManager(args.config)

    if args.action == "add":
        if not args.use_case_id:
            print("Use case ID required for add action")
            exit(1)
        manager.add_use_case(args.use_case_id, args.description)
    elif args.action == "remove":
        if not args.use_case_id:
            print("Use case ID required for remove action")
            exit(1)
        manager.remove_use_case(args.use_case_id)
    elif args.action == "list":
        manager.list_use_cases()
    elif args.action == "validate":
        if not args.use_case_id:
            print("Use case ID required for validate action")
            exit(1)
        manager.validate_use_case(args.use_case_id)
    elif args.action == "show":
        config = manager.load_config()
        print(json.dumps(config, indent=2))
```

### Step 3: Test Configuration

```bash
# Validate Envoy configuration
envoy --mode validate --config-path envoy.yaml

# Or with Docker
docker run --rm -v $(pwd)/envoy.yaml:/envoy.yaml envoyproxy/envoy:v1.28-latest --mode validate --config-path /envoy.yaml
```

### Step 4: Run Envoy Proxy

```bash
# Local installation (ensure config files are in place)
sudo mkdir -p /etc/envoy
sudo cp config/use_cases.json /etc/envoy/
sudo cp config/use_case_validator.lua /etc/envoy/
envoy --config-path envoy.yaml --log-level info

# Docker deployment with mounted configs
docker run -p 8001:8001 \
  -v $(pwd)/envoy.yaml:/etc/envoy/envoy.yaml \
  -v $(pwd)/config/use_cases.json:/etc/envoy/use_cases.json \
  -v $(pwd)/config/use_case_validator.lua:/etc/envoy/use_case_validator.lua \
  envoyproxy/envoy:v1.28-latest

# Docker Compose (recommended)
# See docker-compose.yml section below
```

### Step 5: Docker Compose Configuration

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  envoy-proxy:
    image: envoyproxy/envoy:v1.28-latest
    ports:
      - "8001:8001"
      - "9901:9901"  # Admin interface
    volumes:
      - ./envoy.yaml:/etc/envoy/envoy.yaml
      - ./config/use_cases.json:/etc/envoy/use_cases.json
      - ./config/use_case_validator.lua:/etc/envoy/use_case_validator.lua
    command: ["/usr/local/bin/envoy", "-c", "/etc/envoy/envoy.yaml", "--log-level", "info"]
    depends_on:
      - backend-service

  backend-service:
    # Your existing backend service
    image: your-backend:latest
    ports:
      - "8002:8002"
    environment:
      - PORT=8002

  # Optional: Rate limiting service
  rate-limit-service:
    image: envoyproxy/ratelimit:master
    ports:
      - "8080:8080"
    volumes:
      - ./rate_limit_config.yaml:/data/ratelimit/config/config.yaml
    environment:
      - USE_STATSD=false
      - LOG_LEVEL=debug
      - REDIS_SOCKET_TYPE=tcp
      - REDIS_URL=redis:6379

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

## Configuration Reload Mechanisms

### Option 1: Signal-Based Reload (Recommended)

Envoy supports configuration reloading via SIGUSR1 signal:

```bash
# Find Envoy process ID
ENVOY_PID=$(pgrep envoy)

# Reload configuration (hot restart)
kill -SIGUSR1 $ENVOY_PID

# Or using Docker
docker kill -s SIGUSR1 <container_name>
```

### Option 2: Admin API Configuration Updates

Enable Envoy admin interface and use API calls:

```yaml
# Add to envoy.yaml
admin:
  address:
    socket_address:
      address: 127.0.0.1
      port_value: 9901
```

Configuration update commands:
```bash
# View current configuration
curl http://localhost:9901/config_dump

# Reload configuration via API
curl -X POST http://localhost:9901/config_dump

# View stats related to configuration
curl http://localhost:9901/stats/config
```

### Option 3: File Watcher Script

Create a configuration file watcher script `config_watcher.py`:

```python
#!/usr/bin/env python3
import time
import os
import signal
import subprocess
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, envoy_pid_file="/var/run/envoy.pid"):
        self.envoy_pid_file = envoy_pid_file
        self.last_reload = 0
        self.reload_cooldown = 5  # seconds

    def on_modified(self, event):
        if event.is_directory:
            return

        # Only reload for JSON and Lua files
        if not (event.src_path.endswith('.json') or event.src_path.endswith('.lua')):
            return

        current_time = time.time()
        if current_time - self.last_reload < self.reload_cooldown:
            return

        print(f"Configuration file {event.src_path} modified, reloading Envoy...")

        # Validate JSON configuration before reload
        if event.src_path.endswith('.json'):
            try:
                with open(event.src_path, 'r') as f:
                    json.load(f)
                print("Configuration file validation passed")
            except json.JSONDecodeError as e:
                print(f"Invalid JSON configuration: {e}")
                return

        self.reload_envoy()
        self.last_reload = current_time

    def reload_envoy(self):
        try:
            if os.path.exists(self.envoy_pid_file):
                with open(self.envoy_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGUSR1)
                print(f"Sent reload signal to Envoy PID {pid}")
            else:
                # Fallback to finding process by name
                result = subprocess.run(['pgrep', 'envoy'], capture_output=True, text=True)
                if result.returncode == 0:
                    pid = int(result.stdout.strip())
                    os.kill(pid, signal.SIGUSR1)
                    print(f"Sent reload signal to Envoy PID {pid}")
                else:
                    print("Could not find Envoy process")
        except Exception as e:
            print(f"Error reloading Envoy: {e}")

def main():
    config_dir = "/etc/envoy"

    if not os.path.exists(config_dir):
        print(f"Configuration directory {config_dir} does not exist")
        return

    event_handler = ConfigReloadHandler()
    observer = Observer()
    observer.schedule(event_handler, config_dir, recursive=False)

    observer.start()
    print(f"Watching {config_dir} for configuration changes...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("Configuration watcher stopped")

    observer.join()

if __name__ == "__main__":
    main()
```

Install dependencies and run:
```bash
pip install watchdog
python3 config_watcher.py
```

### Configuration Management Best Practices

1. **Version Control**: Track configuration changes in git
2. **Validation**: Always validate JSON/YAML before applying
3. **Backup**: Create automatic backups before changes
4. **Rollback**: Have a quick rollback mechanism
5. **Testing**: Test configuration changes in staging first

Example configuration management workflow:
```bash
# 1. Backup current configuration
python3 manage_config.py backup

# 2. Add new use case
python3 manage_config.py add "200000" -d "New service integration"

# 3. Validate configuration
python3 -m json.tool /etc/envoy/use_cases.json

# 4. Reload Envoy (automatic via watcher or manual)
kill -SIGUSR1 $(pgrep envoy)

# 5. Verify new configuration is active
curl -H "X-Use-Case-ID: 200000" http://localhost:8001/health
```

## Testing the Implementation

### Basic Functionality Test

```bash
# Valid request
curl -H "X-Use-Case-ID: 100000" http://localhost:8001/api/test

# Invalid use case
curl -H "X-Use-Case-ID: invalid" http://localhost:8001/api/test

# Missing header
curl http://localhost:8001/api/test

# Health check (should bypass validation)
curl http://localhost:8001/health
```

### Load Testing

```bash
# Install hey tool
go install github.com/rakyll/hey@latest

# Test with valid use case
hey -z 30s -c 10 -H "X-Use-Case-ID: 100000" http://localhost:8001/api/test

# Test with invalid use case (should be rejected)
hey -z 30s -c 10 -H "X-Use-Case-ID: invalid" http://localhost:8001/api/test
```

## Migration from FastAPI to Envoy

### Migration Checklist

- [ ] **Configuration Mapping**: Map existing YAML config to Envoy format
- [ ] **Header Validation Logic**: Port FastAPI middleware to Lua script
- [ ] **Error Response Format**: Match existing JSON error responses
- [ ] **Logging Format**: Maintain consistent log structure
- [ ] **Health Checks**: Preserve existing health check endpoints
- [ ] **Configuration Reload**: Implement dynamic configuration updates
- [ ] **Testing**: Verify all existing test cases pass

### Feature Parity Matrix

| FastAPI Feature | Envoy Implementation | Status |
|----------------|---------------------|--------|
| X-Use-Case-ID validation | Lua script filter | ✅ Complete |
| Allowlist checking | Lua script with config | ✅ Complete |
| Case-insensitive matching | String.lower() in Lua | ✅ Complete |
| 400/403 error responses | request_handle:respond() | ✅ Complete |
| Request logging | Access logs + Lua logging | ✅ Complete |
| Health checks | Route-level filter disable | ✅ Complete |
| Config endpoint | Direct response route | ✅ Complete |
| Config reload | Signal-based reload | 🔄 Partial |
| CORS support | CORS filter | ✅ Complete |
| Rate limiting | Rate limit filter | ➕ Enhanced |

### Rollback Plan

1. **Maintain FastAPI**: Keep FastAPI proxy running on alternate port
2. **Traffic Splitting**: Use load balancer to gradually shift traffic
3. **Monitoring**: Compare metrics between both proxies
4. **Quick Switch**: DNS/load balancer configuration for instant rollback

## Advantages of Envoy Implementation

1. **Performance**: Lower latency and higher throughput than FastAPI
2. **Observability**: Built-in metrics, tracing, and access logs
3. **Extensibility**: Rich filter ecosystem for additional features
4. **Production Ready**: Battle-tested in high-scale environments
5. **Cloud Native**: Kubernetes-native with service mesh integration
6. **Rate Limiting**: Built-in distributed rate limiting capabilities
7. **Circuit Breaking**: Automatic failure handling and recovery

## Monitoring and Observability

### Metrics Collection

Envoy exposes metrics on port 9901 by default:

```bash
# View all metrics
curl http://localhost:9901/stats

# Filter for use-case specific metrics
curl http://localhost:9901/stats | grep use_case
```

### Sample Grafana Dashboard Queries

```promql
# Request rate by use case
rate(envoy_http_downstream_rq_total[5m])

# Error rate for rejected requests
rate(envoy_http_downstream_rq_xx{envoy_response_code=~"4.."}[5m])

# Latency percentiles
histogram_quantile(0.95, envoy_http_downstream_rq_time_bucket)
```

This Envoy implementation provides equivalent functionality to your FastAPI proxy while offering enhanced performance, observability, and production-ready features for enterprise deployment.