# Operational shortcuts over the Compose stack ([Runtime](docs/architecture/overview.md#runtime)).
# `docker compose` honours `COMPOSE_PROJECT_NAME` and `COMPOSE_FILE` from the environment, so a
# harness pointed at a different project or file needs no extra option here.

.PHONY: seed-demo

seed-demo:
	docker compose exec -T api leadradar-seed-demo
