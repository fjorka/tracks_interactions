import yaml

from skimage.measure._regionprops import COL_DTYPES, _require_intensity_image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from tracks_interactions.db.db_model import TrackDB

import tracks_interactions.db.db_functions as fdb

def testConfigFile(file_path):
    """
    Test whether the config file is executable.
    """

    # load the config file
    with open(file_path, 'r') as config_file:
        try:
            config = yaml.safe_load(config_file)
        except yaml.YAMLError as exc:
            return False, 'Error loading the config file: {}'.format(exc)

    # test if the database path is correct
    if 'database' not in config:
        return False, 'The database path is missing in the config file.'
    else:
        status, msg = test_database_connection(config['database']['path'])
        if status is False:
            return False, msg

    # test whether signal channels are provided
    if 'signal_channels' not in config:
        return False, 'No signal channels provided in the config file.'
    else:
        for ch in config['signal_channels']:
            if 'zarr' not in ch['path']:
                return False, 'Accepting only zarr files as signal channels.'

    # test requested regionprops functions without signals
    req_regionprops_no_signal = [x['function'] for x in config['cell_measurements'] if x['source']=='regionprops' and not 'channels' in x]
    if not all([x in COL_DTYPES.keys() for x in req_regionprops_no_signal]):
        return False, 'Requested regionprops functions without signals are not supported.'
    
    req_regionprops_signal = [x['function'] for x in config['cell_measurements'] if x['source']=='regionprops' and 'channels' in x]
    if not all([x in _require_intensity_image for x in req_regionprops_signal]):
        return False, 'Requested regionprops functions with signals are not supported.'

    # test track_gardener functions
    

    # test unique measurements names

    # test custom functions

    # test that graphs request existing measurements


def test_database_connection(database_path):
    """
    Test whether the database file is executable.
    """

    try:
        # Create the database engine
        engine = create_engine(f'sqlite:///{database_path}')
        # Initialize a session
        session = sessionmaker(bind=engine)()
        
        return True, "Database connection successful."
    except SQLAlchemyError as e:
        return False, f"Database connection failed: {e}"