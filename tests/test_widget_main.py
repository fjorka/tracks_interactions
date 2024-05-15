import numpy as np
import pytest
from qtpy.QtWidgets import QTabWidget
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import sessionmaker

from tracks_interactions.db.db_model import CellDB, TrackDB
from tracks_interactions.widget.widget_main import TrackGardener


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


def test_main_creates_tabs(viewer):
    """
    Test that the main widget opens a tab widget.
    """

    main_widget = TrackGardener(viewer)

    assert (main_widget.findChildren(QTabWidget) is not None) and (
        len(main_widget.findChildren(QTabWidget)) == 1
    ), f'Expected to find one tab widget, instead got {main_widget.findChildren(QTabWidget)}'


def test_adding_widgets(viewer, db_session):
    """
    Test adding of the widgets.
    """

    main_widget = TrackGardener(viewer)

    # test creating widgets
    ch_list = []
    ch_names = []
    ring_width = 0
    signal_list = []
    graph_list = [{'signals': ['ch0_nuc'], 'colors': 'white'}]
    cell_tags = {}

    main_widget.create_widgets(
        viewer,
        db_session,
        ch_list=ch_list,
        ch_names=ch_names,
        ring_width=ring_width,
        signal_list=signal_list,
        graph_list=graph_list,
        cell_tags=cell_tags,
    )

    assert (
        main_widget.navigation_widget is not None
    ), 'Expected to find a navigation widget, instead got None'
    assert (
        main_widget.modification_widget is not None
    ), 'Expected to find a modification widget, instead got None'
    assert (
        len(main_widget.napari_widgets) == 2
    ), f'Expected to create 2 graph widgets, instead got {len(main_widget.napari_widgets)}'


def test_clearing_widgets(viewer, db_session):
    """
    Test clearing of the widgets.
    """

    main_widget = TrackGardener(viewer)

    # test creating widgets
    ch_list = []
    ch_names = []
    ring_width = 0
    signal_list = []
    graph_list = [{'signals': ['ch0_nuc'], 'colors': 'white'}]
    cell_tags = {}

    main_widget.create_widgets(
        viewer,
        db_session,
        ch_list=ch_list,
        ch_names=ch_names,
        ring_width=ring_width,
        signal_list=signal_list,
        graph_list=graph_list,
        cell_tags=cell_tags,
    )

    # assert that the widgets are added
    assert (
        len(main_widget.napari_widgets) == 2
    ), f'Expected to have 2 graphs, instead got {main_widget.napari_widgets}'

    # run cleaning function
    main_widget.clear_widgets()

    # assert that the widgets are cleared
    assert (
        len(main_widget.napari_widgets) == 0
    ), f'Expected to have 0 graphs, instead got {main_widget.napari_widgets}'
