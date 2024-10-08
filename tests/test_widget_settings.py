import numpy as np
import pytest
from qtpy.QtWidgets import QPushButton
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import sessionmaker

from tracks_interactions.db.db_model import CellDB, TrackDB
from tracks_interactions.widget.widget_settings import SettingsWidget


@pytest.fixture(scope='function')
def db_session():
    # see "./tests/fixtures/test_database_content.PNG" for a visual representation of copied part of the test database
    test_db_path = r'./tests/fixtures/db_2tables_test.db'
    original_engine = create_engine(f'sqlite:///{test_db_path}')
    original_metadata = MetaData()
    original_metadata.reflect(bind=original_engine)

    # Create an in-memory SQLite database
    memory_engine = create_engine('sqlite:///:memory:')
    original_metadata.create_all(memory_engine)

    # Open sessions
    OriginalSession = sessionmaker(bind=original_engine)
    MemorySession = sessionmaker(bind=memory_engine)

    original_session = OriginalSession()
    memory_session = MemorySession()

    # Copy tables
    cells = original_session.query(CellDB).all()
    tracks = original_session.query(TrackDB).all()

    for cell in cells:
        # Create a new instance of CellDB
        new_cell = CellDB()

        # Deep copy
        for key, value in inspect(cell).attrs.items():
            setattr(new_cell, key, value.value)

        memory_session.add(new_cell)

    for track in tracks:
        # Create a new instance of TrackDB
        new_track = TrackDB()

        # Deep copy
        for key, value in inspect(track).attrs.items():
            setattr(new_track, key, value.value)

        memory_session.add(new_track)

    original_session.close()

    yield memory_session

    memory_session.close()


@pytest.fixture(scope='function')
def viewer(make_napari_viewer):

    viewer = make_napari_viewer()
    viewer.add_labels(data=np.zeros([10000, 10000], dtype=int))

    yield viewer

    viewer.close()


def test_open_yaml_dialog(viewer, mocker):
    """
    Test that the dialog to select a file opens.
    """
    set_widget = SettingsWidget(viewer)

    mock_getOpenFileName = mocker.patch(
        'qtpy.QtWidgets.QFileDialog.getOpenFileName',
        return_value=('test.yaml', None),
    )
    loadConfigFile_mock = mocker.patch(
        'tracks_interactions.widget.widget_settings.SettingsWidget.loadConfigFile'
    )
    reorganize_mock = mocker.patch(
        'tracks_interactions.widget.widget_settings.SettingsWidget.reorganizeWidgets'
    )

    set_widget.openFileDialog()

    assert (
        mock_getOpenFileName.called
    ), "The dialog's exec_ method should have been called."
    assert (
        loadConfigFile_mock.called
    ), 'The loadConfigFile method should have been called.'
    assert (
        reorganize_mock.called
    ), 'The reorganizeWidgets method should have been called.'


def test_not_zarr_pathway(viewer):
    """
    Test that the not zarr path is rejected.
    """
    set_widget = SettingsWidget(viewer)

    set_widget.channels_list = [{'path': 'test.tif'}]

    set_widget.loadExperiment()

    exp_status = 'Only zarr files are supported'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be "{exp_status}", instead it is "{viewer.status}"'


def test_experiment_loading(viewer, mocker):
    """
    Test that given 2 arrays, the proper number of layers is created.
    Mocks directly da.from_zarr to avoid loading actual data.
    """
    set_widget = SettingsWidget(viewer)

    set_widget.channels_list = [{'path': 'test1.zarr'}, {'path': 'test2.zarr'}]
    set_widget.labels_settings = {}

    mock_load_zarr = mocker.patch(
        'tracks_interactions.widget.widget_settings.da.from_zarr'
    )
    mock_load_zarr.return_value = np.zeros((1, 10, 10))

    set_widget.loadExperiment()

    # test number of image layers
    layer_im_num = len([x for x in viewer.layers if x._type_string == 'image'])
    assert layer_im_num == 2, f'Expected 2 image layers, got {layer_im_num}'

    # test number of labels layers
    layer_labels_num = len(
        [x for x in viewer.layers if x._type_string == 'labels']
    )
    assert (
        layer_labels_num == 1
    ), f'Expected 1 labels layers, got {layer_labels_num}'


def test_experiment_loading_multiscale(viewer, mocker):
    """
    Test that given 2 multiscale data sets, the proper number of layers is created.
    Mocks method load_zarr to return 2 arrays.
    """
    set_widget = SettingsWidget(viewer)

    set_widget.channels_list = [{'path': 'test1.zarr'}, {'path': 'test2.zarr'}]
    set_widget.labels_settings = {}

    mock_load_zarr = mocker.patch(
        'tracks_interactions.widget.widget_settings.SettingsWidget.load_zarr'
    )
    mock_load_zarr.return_value = [np.zeros((1, 10, 10)), np.zeros((1, 5, 5))]

    set_widget.loadExperiment()

    # test number of image layers
    layer_im_num = len([x for x in viewer.layers if x._type_string == 'image'])
    assert layer_im_num == 2, f'Expected 2 image layers, got {layer_im_num}'

    # test number of labels layers
    layer_labels_num = len(
        [x for x in viewer.layers if x._type_string == 'labels']
    )
    assert (
        layer_labels_num == 1
    ), f'Expected 1 labels layers, got {layer_labels_num}'


def test_yaml_loading(viewer):
    """
    Test that yaml file is loaded properly.
    """
    set_widget = SettingsWidget(viewer)

    set_widget.loadConfigFile('./tests/fixtures/example_config.yaml')

    assert (
        set_widget.experiment_name == 'Test experiment'
    ), f'Expected experiment name to be "Test experiment", got "{set_widget.experiment_name}"'


def test_add_graph(viewer, db_session):
    """
    Test adding a new graph.
    """
    set_widget = SettingsWidget(viewer)
    set_widget.viewer = viewer
    set_widget.session = db_session
    set_widget.signal_list = ['area']
    set_widget.cell_tags = {'tag1': 't'}
    set_widget.napari_widgets = []

    set_widget.add_new_graph_widget()

    assert 'New Graph' in list(
        viewer.window._dock_widgets.keys()
    ), f'Expected a new graph widget to be added, but widgets are {list(viewer.window._dock_widgets.keys())}'


def test_reorg_widgets(viewer, mocker):
    """
    Test reorganizing widgets upon exp loading.
    """
    set_widget = SettingsWidget(viewer)

    mock_load_exp = mocker.patch(
        'tracks_interactions.widget.widget_settings.SettingsWidget.loadExperiment'
    )
    mock_load_track = mocker.patch(
        'tracks_interactions.widget.widget_settings.SettingsWidget.loadTracking'
    )

    set_widget.reorganizeWidgets()

    assert (
        mock_load_exp.called
    ), 'loadExperiment method should have been called'
    assert (
        mock_load_track.called
    ), 'loadTracking method should have been called'

    push_buttons_in_settings = [
        x.text() for x in set_widget.findChildren(QPushButton)
    ]
    assert (
        'Add graph' in push_buttons_in_settings
    ), f'Expected "Add graph" button to be in the settings window, instead buttons: {push_buttons_in_settings}'
