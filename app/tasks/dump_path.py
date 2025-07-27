def dump_path():
    import os, sys
    print("Child CWD:", os.getcwd())
    print("Child sys.path:", sys.path)
