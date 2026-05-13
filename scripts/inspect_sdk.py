"""Inspect Capture SDK to understand registration API call."""
import inspect
import numbersprotocol_capture as cap_module

print("Module file:", cap_module.__file__)
print("Module dir:", dir(cap_module))

# Try to get the Capture class source
try:
    from numbersprotocol_capture import Capture
    print("\nCapture class source:")
    print(inspect.getsource(Capture))
except Exception as e:
    print("Error:", e)
    try:
        print("\nModule source:")
        print(inspect.getsource(cap_module))
    except Exception as e2:
        print("Module source error:", e2)
