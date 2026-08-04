# ext_gui — Desktop Dialogs Extension (tkinter)

Built-in extension providing native desktop dialog blocks via tkinter. Falls back gracefully if tkinter is unavailable.

## Loading

```arb
loadExt("ext_gui", "python");
```

## Blocks (10)

| Block | Description |
|-------|-------------|
| `gui.dialog(message, title: "...")` | Show a message dialog. |
| `gui.input(prompt, default, title: "...")` | Show an input dialog. Returns the entered string. |
| `gui.yesNo(prompt, title: "...")` | Show a yes/no dialog. Returns boolean. |
| `gui.fileOpen(title: "...")` | Show a file open dialog. Returns the selected path. |
| `gui.fileSave(title: "...")` | Show a file save dialog. Returns the selected path. |
| `gui.colorPicker()` | Show a color picker. Returns the hex color string. |
| `gui.password(prompt, title: "...")` | Show a password input dialog (masked). Returns the password string. |
| `gui.notify(title, message)` | Show a notification dialog. |
| `gui.menu(title, items)` | Show a dropdown menu. `items` is pipe-separated. Returns the selected item. |
| `gui.form(title, fields)` | Show a multi-field form. `fields` is `"Name:default\|Email:\|Age:0"`. Returns a dict. |

## Usage Examples

```arb
loadExt("ext_gui", "python");

gui.dialog("Hello!");                       // message box
gui.input("Enter name:", "World");           // input dialog
gui.yesNo("Continue?");                      // yes/no dialog
gui.fileOpen();                              // file picker
gui.fileSave();                              // save dialog
gui.colorPicker();                           // color picker
gui.password("Enter password:");            // masked input
gui.notify("Title", "Message");              // notification
gui.menu("Choose:", "A|B|C");                 // dropdown menu
gui.form("User Info", "Name:|Email:|Age:0"); // multi-field form
```

## Grammar

```
gui_dialog   ::= "gui.dialog" "(" expr ("," tag)* ")"
gui_input_d  ::= "gui.input" "(" expr ("," expr)? ("," tag)* ")"
gui_yesno    ::= "gui.yesNo" "(" expr ("," tag)* ")"
gui_fileopen ::= "gui.fileOpen" "(" ("," tag)* ")"
gui_filesave ::= "gui.fileSave" "(" ("," tag)* ")"
gui_colorpk  ::= "gui.colorPicker" "(" ")"
gui_password ::= "gui.password" "(" expr ("," tag)* ")"
gui_notify   ::= "gui.notify" "(" expr "," expr ")"
gui_menu_d   ::= "gui.menu" "(" expr "," expr ")"
gui_form_d   ::= "gui.form" "(" expr "," expr ")"
```
