# Foundry Runtime Audit

## Purpose

Determine whether a codebase is truly using an Azure AI Foundry **project/runtime abstraction** or merely calling Azure OpenAI directly.

## When to use

- A repo claims “Foundry” usage, but behavior is unclear
- Migration parity depends on matching auth/client/runtime semantics
- You need evidence from real code, not naming or branch assumptions

## Procedure

1. **Inspect package references**
   - C#: check `.csproj` for `Azure.AI.Projects` or project-runtime packages
   - Python: check `pyproject.toml` / requirements for Foundry/project SDKs

2. **Inspect runtime construction**
   - Direct Azure OpenAI usually looks like:
     - C#: `new AzureOpenAIClient(endpoint, credential).GetChatClient(deployment)`
     - Python: `AzureOpenAI(azure_endpoint=..., api_version=...)`
   - Foundry-project usage should create a project/client/runtime object, not just endpoint + deployment

3. **Check endpoint shape**
   - `*.cognitiveservices.azure.com` usually indicates direct Azure OpenAI resource usage
   - Project-style config should expose explicit project/runtime concepts

4. **Search the full repo history if needed**
   - Search for `Foundry`, `AIProject`, `Azure.AI.Projects`, project-runtime types
   - Do not infer architecture from README wording alone

5. **Run the real entrypoint**
   - Confirm what the live path actually tries to construct
   - Even if startup fails, early initialization often proves whether the path is direct Azure OpenAI or project-backed

## Output template

- **Current runtime type:** direct Azure OpenAI / Foundry project runtime
- **Evidence:** package refs, constructor calls, endpoint form, live run notes
- **Parity invariant:** what downstream ports must match
- **Gap call:** whether the gap is in the port, or already in the source system
