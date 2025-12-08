try:
    import flask
    import dashscope
    print("Imports successful")
except ImportError as e:
    print(f"Import failed: {e}")
