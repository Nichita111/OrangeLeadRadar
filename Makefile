# Operational shortcuts over the Compose stack ([Runtime](docs/architecture/overview.md#runtime)).
# `docker compose` honours `COMPOSE_PROJECT_NAME` and `COMPOSE_FILE` from the environment, so a
# harness pointed at a different project or file needs no extra option here.

.PHONY: seed-demo refresh-demo seed-labels export-labels

seed-demo:
	docker compose exec -T api leadradar-seed-demo

refresh-demo:
	docker compose exec -T api leadradar-refresh-demo

seed-labels:
	docker compose exec -T api leadradar-seed-labels

# `fixtures/` is read-only inside the container, so the export is written on the host.
export-labels:
	docker compose exec -T api leadradar-export-labels > fixtures/evaluation_items.json
