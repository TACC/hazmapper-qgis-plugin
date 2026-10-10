.PHONY: test-noqgis test-qgis test-qgis-all zip

PLUGIN_PATH = Hazmapper

VERSION ?= $(shell awk -F= '/^version=/{gsub(/[ \t]/,""); print $$2}' $(PLUGIN_PATH)/metadata.txt)

# Fast, pure-Python tests (no QGIS)
test-noqgis:
	uv run pytest -m no_qgis_required

# QGIS integration tests in Docker (default: 3.44 LTR); override with: make test-qgis QGIS_IMAGE=qgis/qgis:4.2
QGIS_IMAGE ?= qgis/qgis:3.44
# The QGIS images are amd64-only; on Apple Silicon they run under emulation
DOCKER_PLATFORM ?= linux/amd64
test-qgis:
	docker run --rm --platform $(DOCKER_PLATFORM) \
	  -e QT_QPA_PLATFORM=offscreen \
	  -v "$$(pwd)":/work -w /work \
	  $(QGIS_IMAGE) \
	  bash -euxo pipefail -c './scripts/run_qgis_tests.sh'

# QGIS integration tests against both a Qt5 (QGIS 3) and a Qt6 (QGIS 4) build
QGIS_IMAGES_ALL ?= qgis/qgis:3.44 qgis/qgis:4.2
test-qgis-all:
	@for image in $(QGIS_IMAGES_ALL); do \
	  echo "=== $$image ==="; \
	  $(MAKE) test-qgis QGIS_IMAGE=$$image || exit 1; \
	done

# Build ZIP using the version from metadata.txt
zip:
	@echo "Packaging version $(VERSION)"
	uv run qgis-plugin-ci package "$(VERSION)" --allow-uncommitted
