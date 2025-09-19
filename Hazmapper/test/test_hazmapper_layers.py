import pytest
from unittest.mock import patch, Mock, ANY


@pytest.mark.qgis_required
@patch("Hazmapper.hazmapper_layers.QgsProject")
@patch("Hazmapper.hazmapper_layers.QgsLayerTreeGroup")
def test_create_or_replace_main_group_new(mock_tree_group, mock_project):
    from Hazmapper.hazmapper_layers import create_main_group

    # Mock the QGIS project and layer tree
    mock_root = Mock()
    mock_root.children.return_value = []
    mock_project.instance.return_value.layerTreeRoot.return_value = mock_root

    # Mock the group creation
    mock_group = Mock()
    mock_tree_group.return_value = mock_group

    # Act
    result = create_main_group("Test Project", "uuid-123")

    # Assert
    mock_tree_group.assert_called_once_with("Test Project (uuid-123)")
    mock_group.setCustomProperty.assert_any_call("hazmapper_project_uuid", "uuid-123")
    mock_group.setCustomProperty.assert_any_call(
        "hazmapper_qgis_internal_group_uuid", ANY
    )
    mock_root.insertChildNode.assert_called_once_with(0, mock_group)
    assert result is mock_group
