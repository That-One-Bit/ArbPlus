import subprocess 
from pathlib import Path 
import sys 

home = Path.cwd()

print("01_Hello_World - Basic Hello World in Arb\n02_Input - Taking User Input and Repeating It Back\n03_Colored_Output - ") 

while True: 
    print('For the following, give the number in (0#) format. 01, 02, and so on. Type "custom" to provide your own file.') 
    match (input("What example would you like to run: ")): 
        case "01": 
            arbfile = "./01_Hello_World.arb" 
        case "02": 
            arbfile = "./02_Input.arb" 
        case "03": 
            arbfile = "./03_Colored_Output.arb" 
        case "custom": 
            arbfile = input("Enter the path to your Arb(plus) file: ") 
        case _: 
            print("Invalid input. Please enter 01, 02, or 03.") 
            sys.exit() 

    interp = home / "interpreter.py" 
    script_dir = home / "Examples" / "Basic_IO"

    # Run Arb script in new window
    subprocess.Popen(["cmd.exe", "/K", sys.executable, str(interp), arbfile], cwd=script_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)
    exit()
