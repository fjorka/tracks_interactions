import numpy as np

from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import make_transient, sessionmaker

import pytest
from unittest.mock import Mock

from vispy.util.event import Event

from tracks_interactions.db.db_model import NO_PARENT, CellDB, TrackDB
from tracks_interactions.widget.widget_navigation import TrackNavigationWidget

import napari
from qtpy.QtCore import Qt

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
    viewer.add_labels(data=np.zeros([10000,10000],dtype=int))

    yield viewer

    viewer.close()

def test_select_label(qtbot,viewer,db_session):
    """
    Test selection of a cell with a right click.
    """    

    track_navigation_widget = TrackNavigationWidget(viewer,db_session)

    # position for a cell to test selection
    viewer.dims.set_point(0, 10)
       canvas: SceneCanvas = viewer.window.qt_viewer.canvas
    # Translate position to canvas coordinates
    vispy_pos = vispy_utils.qt_to_vispy(pos, canvas)
    # Create the mouse event with the right button
    mouse_event = Event(type='mouse_press', pos=vispy_pos, button=2, modifiers=[])
    # Emit the mouse press event through the visual canvas
    canvas.events.mouse_press(mouse_event)
    event = Event(type='mouse_press', pos=(5051.0, 4569.0), button=2)
    viewer.window.qt_viewer.canvas.events.mouse_press(event)

    assert track_navigation_widget.labels.selected_label == 20422


def test_go_to_track_beginning(qtbot,viewer,db_session):
    """
    Test moving to the beginning of the track.
    """

    track_navigation_widget = TrackNavigationWidget(viewer,db_session)

    qtbot.addWidget(track_navigation_widget)

    # set viewer position to 10
    viewer.dims.set_point(0, 10)

    # select active track
    track_navigation_widget.labels.selected_label = 20422

    # Simulate clicking the "start track" button
    qtbot.mouseClick(track_navigation_widget.start_track_btn, Qt.LeftButton)

    assert viewer.dims.current_step[0] == 0


def test_go_to_track_end(qtbot, viewer,db_session):
    """
    Test moving to the end of the track.
    """

    track_navigation_widget = TrackNavigationWidget(viewer,db_session)

    qtbot.addWidget(track_navigation_widget)

    # set viewer position to 10
    viewer.dims.set_point(0, 10)

    # select active track
    track_navigation_widget.labels.selected_label = 20422

    # Simulate clicking the "start track" button
    qtbot.mouseClick(track_navigation_widget.end_track_btn, Qt.LeftButton)

    assert viewer.dims.current_step[0] == 42

def test_center_on_cell(qtbot, viewer,db_session):
    """
    Test that the viewer centers on cell when requested.
    """

    track_navigation_widget = TrackNavigationWidget(viewer,db_session)

    qtbot.addWidget(track_navigation_widget)

    # set viewer position to 10
    viewer.dims.set_point(0, 10)

    # select active track
    track_navigation_widget.labels.selected_label = 20422

    # test of default which is following the selected cell
    np.testing.assert_allclose(viewer.camera.center,(0.0, 5051.0, 4569.0))

    # test upon changing frame
    viewer.dims.set_point(0, 11)
    np.testing.assert_allclose(viewer.camera.center,(0.0, 5049.0, 4570.0))

    # test upon unclicking following
    track_navigation_widget.follow_object_checkbox.setChecked(False)
    viewer.dims.set_point(0, 10)
    np.testing.assert_allclose(viewer.camera.center,(0.0, 5049.0, 4570.0))

    # test upon clicking centering
    qtbot.mouseClick(track_navigation_widget.center_object_btn, Qt.LeftButton)
    np.testing.assert_allclose(viewer.camera.center,(0.0, 5051.0, 4569.0))

    # test upon activating following
    viewer.dims.set_point(0, 11)
    track_navigation_widget.follow_object_checkbox.setChecked(True)
    np.testing.assert_allclose(viewer.camera.center,(0.0, 5049.0, 4570.0))