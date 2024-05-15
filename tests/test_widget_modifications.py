from unittest.mock import MagicMock

import numpy as np
import pytest
from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QDialog, QPushButton
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


def test_select_label_to_t_boxes(viewer, db_session):
    """
    Test selection of a label and modifications of 'previous' and 'active' fields.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # position for a cell to test selection
    first_label = 20422
    modification_widget.labels.selected_label = first_label

    assert (
        modification_widget.T2_box.value()
        == modification_widget.labels.selected_label
    ), f'Expected active label to be {modification_widget.selected_label}, instead {modification_widget.T2_box.value()}.'

    modification_widget.labels.selected_label = 20423
    assert (
        modification_widget.T2_box.value()
        == modification_widget.labels.selected_label
    ), f'Expected active label to be {modification_widget.selected_label}, instead {modification_widget.T2_box.value()}.'
    assert (
        modification_widget.T1_box.value() == first_label
    ), f'Expected previous label to be {first_label}, instead {modification_widget.T1_box.value()}.'


def test_t_box_to_label(viewer, db_session):
    """
    Test translating of the T2 field to the selected label.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # position for a cell to test selection
    sel_label = 5
    modification_widget.T2_box.setValue(sel_label)
    modification_widget.T2_box.editingFinished.emit()

    assert (
        modification_widget.labels.selected_label == sel_label
    ), f'Expected selected label to be {modification_widget.T2_box.value()}, instead it is {modification_widget.labels.selected_label}.'


def test_adding_new_track(qtbot, viewer, db_session):
    """
    Test adding new track.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    modification_widget.new_track_function()

    assert (
        modification_widget.labels.selected_label == 37404
    ), f'Expected selected label to be 37404, instead it is {modification_widget.labels.selected_label}.'


def test_cut_cell_function(qtbot, viewer, db_session):
    """
    Test function to cut a cell - true cut.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    modification_widget.labels.selected_label = 20422
    viewer.dims.set_point(0, 20)

    modification_widget.cut_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == 37404
    ), f'Expected selected track to be a new track - 37404, instead it is {modification_widget.labels.selected_label}.'


def test_cut_cell_function_mistake_click(qtbot, viewer, db_session):
    """
    Test function to cut a cell - mistake.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    sel_label = 20422
    modification_widget.labels.selected_label = sel_label
    viewer.dims.set_point(0, 60)

    modification_widget.cut_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == sel_label
    ), f'Expected selected track to be a new track - {sel_label}, instead it is {modification_widget.labels.selected_label}.'


def test_cut_cell_function_mitosis(qtbot, viewer, db_session):
    """
    Test function to cut a cell from mitosis.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    starting_track = 37402
    modification_widget.labels.selected_label = starting_track
    viewer.dims.set_point(0, 35)

    modification_widget.cut_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == 37402
    ), f'Expected selected track to be {starting_track}, instead it is {modification_widget.labels.selected_label}.'


def test_del_cell_function(qtbot, viewer, db_session):
    """
    Test function to delete an entire track.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    starting_track = 37402
    modification_widget.labels.selected_label = starting_track

    modification_widget.del_track_function()

    # check that the new selected label is zero, because the track was deleted
    assert (
        modification_widget.labels.selected_label == 0
    ), f'Expected selected track to be 0, instead it is {modification_widget.labels.selected_label}.'


def test_del_cell_function_no_cell(qtbot, viewer, db_session):
    """
    Test function to delete an entire track, not found.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    starting_track = 37402
    modification_widget.labels.selected_label = starting_track
    no_track = 333
    modification_widget.labels.selected_label = no_track

    modification_widget.del_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == no_track
    ), f'Expected selected track to be {starting_track}, instead it is {modification_widget.labels.selected_label}.'
    exp_status = 'Track not found'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_merge_cell_function(qtbot, viewer, db_session):
    """
    Test function to merge two tracks.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 37402
    active_track = 20428
    viewer.dims.set_point(0, 130)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    # merge tracks
    modification_widget.merge_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == previous_track
    ), f'Expected selected track to be {previous_track}, instead it is {modification_widget.labels.selected_label}.'


def test_merge_cell_function_too_early(qtbot, viewer, db_session):
    """
    Test function to merge two tracks.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 20428
    active_track = 37402
    viewer.dims.set_point(0, 70)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    # merge tracks
    modification_widget.merge_track_function()

    exp_status = "Error - cannot merge to a track that hasn't started yet."
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_merge_cell_function_same_cell(qtbot, viewer, db_session):
    """
    Test function to merge two tracks.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)
    modification_widget.T2_box.setValue(37402)
    modification_widget.T1_box.setValue(37402)

    viewer.dims.set_point(0, 130)

    # merge tracks
    modification_widget.merge_track_function()

    exp_status = 'Error - cannot merge a track with itself.'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_connect_cell_function(qtbot, viewer, db_session):
    """
    Test function to connect two tracks.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 37402
    active_track = 20428
    viewer.dims.set_point(0, 130)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    # merge tracks
    modification_widget.connect_track_function()

    # check that the new selected label is a new track
    assert (
        modification_widget.labels.selected_label == active_track
    ), f'Expected selected track to be {active_track}, instead it is {modification_widget.labels.selected_label}.'


def test_connect_cell_function_clean(viewer, db_session, mocker):
    """
    Test function to connect two tracks.
    Active track doesn't need to be cut.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 37402
    active_track = 20425
    viewer.dims.set_point(0, 207)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    # call the function to connect the tracks
    modification_widget.connect_track_function()

    exp_status = (
        f'Track {active_track} has been connected to {previous_track}.'
    )
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_connect_cell_function_clean_call_db(viewer, db_session, mocker):
    """
    Test function to connect two tracks.
    Active track doesn't need to be cut.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 37402
    active_track = 20425
    viewer.dims.set_point(0, 207)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    mock_func_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.integrate_trackDB'
    )
    mock_func_db.return_value = None, None

    # call the function to connect the tracks
    modification_widget.connect_track_function()

    # assert calling the database function
    assert (
        mock_func_db.called
    ), f'{mock_func_db.name} should have been called but it was not.'


def test_connect_cell_function_same_cell(qtbot, viewer, db_session):
    """
    Test function to connect two tracks when requested for the same tracks.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)
    modification_widget.T2_box.setValue(37402)
    modification_widget.T1_box.setValue(37402)

    viewer.dims.set_point(0, 130)

    # merge tracks
    modification_widget.connect_track_function()

    exp_status = 'Error - cannot connect a track with itself.'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_connect_cell_function_too_early(qtbot, viewer, db_session):
    """
    Test function to connect two tracks when the receiver track didn't start yet.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    previous_track = 20428
    active_track = 37402
    viewer.dims.set_point(0, 70)

    # populate T1 and T2 spinboxes by selection
    modification_widget.labels.selected_label = previous_track
    modification_widget.labels.selected_label = active_track

    # merge tracks
    modification_widget.connect_track_function()

    exp_status = "Error - cannot connect to a track that hasn't started yet."
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'


def test_add_note_to_track(qtbot, viewer, db_session):
    """
    Test function to add a free format note to a track.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # Call the function to test
    tag_widget = modification_widget.add_note_tag_buttons()

    # Verify that the note button is added even when tags are not present
    # note button doesn't have text, just icon
    assert (
        len(tag_widget.findChildren(QPushButton)) == 1
    ), f'Expected a single a button to be found, but instead {len(tag_widget.findChildren(QPushButton))} buttons found.'

    btn = tag_widget.findChildren(QPushButton)[0]

    original_exec = QDialog.exec_
    QDialog.exec_ = MagicMock(
        return_value=1
    )  # Assuming 1 is the 'accepted' return value

    # Use QTest to click the button, it does not require the window to be visible
    QTest.mouseClick(btn, Qt.LeftButton)

    # Check that the exec was called, indicating the dialog was 'opened'
    assert (
        QDialog.exec_.called
    ), "The dialog's exec_ method should have been called."

    # Restore the original method after the test to avoid side effects
    QDialog.exec_ = original_exec


def test_save_note(viewer, db_session):
    """
    Test function to add a free format note to a track.
    Only the behaviour of the interface.
    Database modifications are tested separately.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    my_note = 'test'
    mock_event = MagicMock()
    mock_event.toPlainText.return_value = my_note
    modification_widget.text_edit = mock_event
    mock_dialog = MagicMock()
    modification_widget.dialog = mock_dialog
    active_label = 20422
    modification_widget.labels.selected_label = active_label

    # Call the method
    modification_widget.save_note()

    exp_status = f'Note for track {active_label} saved in the database.'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be {exp_status}, instead it is {viewer.status}'

    assert (
        modification_widget.current_note == my_note
    ), f'Expected current.note to be {my_note}, instead it is {modification_widget.current_note}'


def test_mod_cell_function_deletion(viewer, db_session, mocker):
    """
    Test saving modifications of a cell object to a database.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # labels are not really build unless navigation widget is built
    cell_id = '20422'
    viewer.dims.set_point(0, 0)

    mock_cell = MagicMock()
    mock_cell.track_id = cell_id
    modification_widget.labels.metadata['query'] = [mock_cell]

    mock_remove_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.remove_CellDB'
    )

    modification_widget.mod_cell_function()

    assert mock_remove_db.called, 'remove_CellDB should have been called'


def test_mod_cell_function_addition(viewer, db_session, mocker):
    """
    Test saving modifications of a cell object to a database.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # set position
    viewer.dims.set_point(0, 0)

    # change labels
    modification_widget.labels.data[0:2, 0:2] = 5

    # mock the query remembered by labels
    modification_widget.labels.metadata['query'] = []

    mock_func_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.add_new_CellDB'
    )

    modification_widget.mod_cell_function()

    assert mock_func_db.called, 'add_new_CellDB should have been called'


def test_mod_cell_function_modification(viewer, db_session, mocker):
    """
    Test saving modifications of a cell object to a database.
    """

    modification_widget = ModificationWidget(viewer, db_session)

    # set position
    viewer.dims.set_point(0, 0)

    # change labels
    modification_widget.labels.data[0:2, 0:2] = 2

    # mock the query remembered by labels
    cell_id = 2
    pos = 100
    viewer.dims.set_point(0, 0)

    mock_cell = MagicMock()
    mock_cell.track_id = cell_id
    mock_cell.row = pos
    mock_cell.col = pos
    modification_widget.labels.metadata['query'] = [mock_cell]

    mock_func_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.add_new_CellDB'
    )
    mock_remove_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.remove_CellDB'
    )

    modification_widget.mod_cell_function()

    assert mock_remove_db.called, 'remove_CellDB should have been called'
    assert mock_func_db.called, 'add_new_CellDB should have been called'

    exp_status = '2 has been modified'
    assert (
        viewer.status == exp_status
    ), f'Expected status of the viewer to be "{exp_status}", instead it is "{viewer.status}"'


def test_tags_create_buttons(viewer, db_session, mocker):
    """
    Test creating adding tag buttons when a dictionary is provided.
    """

    tag_dictionary = {'modified': 'x', 'tag1': 'a', 'tag2': 'b'}

    modification_widget = ModificationWidget(
        viewer, db_session, tag_dictionary=tag_dictionary
    )
    tag_widget = modification_widget.add_note_tag_buttons()

    # Verify that the note button is added even when tags are not present
    assert (
        len(tag_widget.findChildren(QPushButton)) == 3
    ), f'Expected 3 buttons to be found, but instead {[x.text() for x in tag_widget.findChildren(QPushButton)]} buttons found.'


def test_tags_call_annotation(viewer, db_session, mocker):
    """
    Test calling annotating function when a button is clicked
    """

    tag_dictionary = {'modified': 'x', 'tag1': 'a', 'tag2': 'b'}

    modification_widget = ModificationWidget(
        viewer, db_session, tag_dictionary=tag_dictionary
    )
    tag_widget = modification_widget.add_note_tag_buttons()

    viewer.dims.set_point(0, 0)
    modification_widget.labels.selected_label = 20422

    mock_func_db = mocker.patch(
        'tracks_interactions.widget.widget_modifications.fdb.tag_cell'
    )
    mock_func_db.return_value = 'Test'

    # any tag button beyond the note (the first one)
    btn = tag_widget.findChildren(QPushButton)[1]

    # Use QTest to click the button, it does not require the window to be visible
    QTest.mouseClick(btn, Qt.LeftButton)

    assert (
        mock_func_db.called
    ), f"Expected an annotating function to be called for {btn.text()}, but it wasn't."
