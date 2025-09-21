# Light Proxy for restricted access to DataBricks Genie API

Light poc to restrict access to DataBrikcs Genie API basedon some policy.
We will implement a lightweight proxy that checks on policy condition before allowing or blocking traffic to [DataBricks Genie API]https://docs.databricks.com/aws/en/genie/conversation-api)



![proxy image](images/proxy_uc_ginie.drawio.png)

## Dependencies
Install `uv` as package manager if you haven't already
```bash
pip install uv
```

To install them run
```bash
uv sync
```



## Usage
Run:
```bash
uv run main.py
```
---

## Requirements

### Header naming convention
The Client will emit (or not) a custom http header: `X-Usecase-ID`.

### Client Implementation
- Include the header on every relevant request
- Set it at the HTTP client/library level rather than per-request when possible
- Use configuration or environment variables to manage the usecase-id value
- Use a usecase-id value that is logged into our LUMA governance DB

### Proxy Configuration Considerations
#### Header Validation:

- Implement allowlists of valid usecase-id values
- Reject requests with malformed or unknown values
- Consider case sensitivity (recommend case-insensitive matching)

#### Traffic Control Logic:
- Use the header for access control (we can also use it down the road for routing and rate limiting)
 - Allow if `X-Usecase-ID` exists AND the value is in the allowlists
 - Block if the `X-Usecase-ID` is missng OR the value is missing from the allowlists


#### Logging and Oservability
- Log header values for audit monitoring and debugging


