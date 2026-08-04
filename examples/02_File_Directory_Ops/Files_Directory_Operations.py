import subprocess 
from pathlib import Path 
import sys 

#TODO Use map/dict for examples and call via loop/map lookup
home = Path.cwd()

print("01 - Reading Files") 

while True:
    match (input("What example would you like to run? 01, 02 and so on, type custom to provide your own file: ")): 
        case "01": 
            arbfile = "./01_File_Reading.arb" 
        case "02": 
            arbfile = "./02_File_Writing.arb" 
        case "03": 
            arbfile = "./03_Colored_Output.arb" 
        case "04":
            arbfile = "./04_Variables.arb"
        case "05":
            arbfile = "./05_String_Concatenation.arb"
        case "06":
            arbfile = "./06_String_Interpolation.arb"
        case "custom": 
            arbfile = input("Enter the path to your Arb(plus) file: ") 
        case _: 
            input("Invalid input. Please enter a valid argument. The terminal will now close. ")
            sys.exit() 

    interp = "S:\\Development\\ARBplus\\interpreter.py"
    script_dir = "S:\\Development\\ARBplus\\Examples\\01_Basic_IO"

    # Run Arb script in new window
    subprocess.Popen(
            ["cmd", 
            "/k", 
            f"title {arbfile} &", 
            sys.executable, 
            str(interp), 
            str(arbfile)
            ],
            cwd=str(script_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    input("\n Press enter to continue: ")
    print("\n")