.PHONY: test test-qgis test-qgis-debug

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
