"""
/***************************************************************************
 HazmapperPlugin
  A QGIS plugin to display Hazmapper map/project data using QGIS
 """

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *

from .hazmapper_plugin_dockwidget import HazmapperPluginDockWidget
import os.path


class HazmapperPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance passed by QGIS that allows
            manipulation of the QGIS application at runtime.
        :type iface: QgsInterface
        """
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", "HazmapperPlugin_{}.qm".format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&Hazmapper")

        self.pluginIsActive = False
        self.dockwidget = None

    # -------------------------------------------------------------------------
    # Translation helper
    def tr(self, message):
        return QCoreApplication.translate("HazmapperPlugin", message)

    # -------------------------------------------------------------------------
    # Toolbar/Menu Action Helper
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar."""

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)  # Global Plugins toolbar

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    # -------------------------------------------------------------------------
    # GUI initialization
    def initGui(self):
        """Create the toolbar button (Plugins toolbar only)."""

        icon_path = ":/plugins/hazmapper_plugin/Hazmapper.svg"
        self.add_action(
            icon_path,
            text=self.tr("Hazmapper Tools"),
            callback=self.toggle_dockwidget,  # Toggle instead of always run
            add_to_menu=False,
            add_to_toolbar=True,
            parent=self.iface.mainWindow(),
        )

    # -------------------------------------------------------------------------
    # Cleanup
    def unload(self):
        """Remove plugin icon and menu items when plugin is unloaded."""
        for action in self.actions:
            self.iface.removeToolBarIcon(action)
            self.iface.removePluginMenu(self.menu, action)

        # Close dockwidget if open
        if self.dockwidget and self.dockwidget.isVisible():
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget = None
            self.pluginIsActive = False

    def toggle_dockwidget(self):
        """Toggle the dockwidget open/closed when toolbar button is clicked."""

        # If no dockwidget exists, create it
        if not self.dockwidget:
            self.dockwidget = HazmapperPluginDockWidget(
                iface=self.iface, plugin_dir=self.plugin_dir
            )
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

        # If already visible, close it
        if self.pluginIsActive and self.dockwidget.isVisible():
            self.iface.removeDockWidget(self.dockwidget)
            self.pluginIsActive = False
        else:
            # Show it on the right instead of top
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            self.pluginIsActive = True

    def onClosePlugin(self):
        """Called when dockwidget emits closingPlugin signal."""
        self.pluginIsActive = False
