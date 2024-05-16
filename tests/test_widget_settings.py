import numpy as np
import pytest
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
