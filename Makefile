.PHONY: test test-qgis test-qgis-debug

PLUGIN_PATH = hazmapper_plugin

VERSION ?= $(shell awk -F= '/^version=/{gsub(/[ \t]/,""); print $$2}' $(PLUGIN_PATH)/metadata.txt)

# Fast, pure-Python tests (no QGIS)
test:
	uv run pytest -m no_qgis_required

# QGIS integration tests in Docker (default: 3.34); override with: make test-qgis QGIS_IMAGE=qgis/qgis:release-3_28
QGIS_IMAGE ?= qgis/qgis:release-3_34
test-qgis:
	docker run --rm \
	  -e QT_QPA_PLATFORM=offscreen \
	  -v "$$(pwd)":/work -w /work \
	  $(QGIS_IMAGE) \
	  bash -euxo pipefail -c './scripts/run_qgis_tests.sh'

# Build ZIP using the version from metadata.txt
zip:
	@echo "Packaging version $(VERSION)"
	uv run qgis-plugin-ci package "$(VERSION)" --allow-uncommitted
