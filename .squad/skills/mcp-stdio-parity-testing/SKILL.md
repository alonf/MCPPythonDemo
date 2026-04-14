# MCP STDIO Parity Testing Skill

## When to use

Use this pattern when a repo needs reviewer-grade validation for:

- a Python MCP stdio server
- a lecture/demo parity path against another reference implementation
- a client-side LLM workflow that should fail cleanly when credentials are missing

## Pattern

1. **Validate the server with the official SDK client**
   - start the server with `StdioServerParameters`
   - run `initialize`
   - assert tool discovery
   - call the target tool on happy path
   - call an invalid tool and confirm an error payload, not a crash

2. **Add negative-path unit coverage around live system reads**
   - patch `/proc` readers
   - require zero/fallback payloads instead of exceptions

3. **Split client validation into two lanes**
   - fake-model/unit lane for deterministic tool-calling orchestration
   - real CLI lane with credentials stripped so missing-config messaging is tested exactly as users see it

4. **Make smoke output human-readable**
   - print the live server payload
   - print the validated client failure message
   - keep transport details out of the final QA summary

## Files in this repo that follow the pattern

- `tests/test_m1_smoke.py`
- `tests/test_system_info.py`
- `tests/test_client.py`
- `scripts/smoke_test.py`
