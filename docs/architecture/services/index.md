# Services

* [API service](api.md) - The FastAPI process - its responsibilities and boundary, the tables and rules it owns, request handling, transactions, enqueueing, the interactive AI calls it makes, and its configuration keys.
* [Worker service](worker.md) - The background process - job queue and priorities, run lifecycle and stages, the LangGraph signal graph, the AI gateway with its Jev and OpenRouter adapters, the source plug-in adapters, the scheduler and housekeeping, and every pipeline configuration key.
* [Frontend](frontend.md) - The React web client - stack, routes and roles, navigation and service selector, screen states, screen labels, formatting, polling, tables and accessibility - with the shell-level FR rows every screen obeys and its configuration keys.
