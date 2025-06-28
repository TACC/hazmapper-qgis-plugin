from qgis.core import QgsApplication
import pytest
import sys

# Init QGIS application
qgs = QgsApplication([], False)
app.setLogLevel(Qgis.Warning)  # or Qgis.Critical
qgs.initQgis()

# Run tests
exit_code = pytest.main(["hazmapper_plugin/test"])

# Cleanup
qgs.exitQgis()
sys.exit(exit_code)

