from unittest.mock import Mock

import numpy as np
import pytest
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import sessionmaker

from tracks_interactions.db.db_model import CellDB, TrackDB
from tracks_interactions.widget.widget_modifications import ModificationWidget


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


def test_select_label_to_t_boxes(qtbot, viewer, db_session):
    """
    Test selection of a label and modifications of 'previous' and 'active' fields.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # position for a cell to test selection
    modification_widget.labels.selected_label = 20422

    assert modification_widget.T2_box.value() == modification_widget.labels.selected_label, f'Expected active label to be {modification_widget.selected_label}, instead {modification_widget.T2_box.value()}.'

    modification_widget.labels.selected_label = 20423
    assert modification_widget.T2_box.value() == modification_widget.labels.selected_label, f'Expected active label to be {modification_widget.selected_label}, instead {modification_widget.T2_box.value()}.'
    assert modification_widget.T1_box.value() == 20422, f'Expected previous label to be 20422, instead {modification_widget.T1_box.value()}.'

def test_t_box_to_label(qtbot, viewer, db_session):
    """
    Test translating of the T2 field to the selected label.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # position for a cell to test selection
    modification_widget.T2_box.setValue(5)
    modification_widget.T2_box.editingFinished.emit()

    assert modification_widget.labels.selected_label == 5, f'Expected selected label to be {modification_widget.T2_box.value()}, instead it is {modification_widget.labels.selected_label}.'

def test_adding_new_track(qtbot, viewer, db_session):
    """
    Test adding new track.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    modification_widget.new_track_function()

    assert modification_widget.labels.selected_label == 37404, f'Expected selected label to be 37404, instead it is {modification_widget.labels.selected_label}.'

def test_mod_cell_function(qtbot, viewer, db_session):
    """
    Test saving modifications of a cell object to a database.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    modification_widget.
