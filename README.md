# Deresute Tools

For the compiled releases optimized for Windows 10, please refer to the [main branch](https://github.com/deresute-tools/deresute-tools).

## Table of Contents
- [Setup](#setup-)
  - [Download the source code from the Download ZIP button.](#download-the-source-code-from-the-download-zip-button-)
  - [Install Python](#install-python-)
    - [Extra Note for Windows 7](#extra-note-for-windows-7-)
  - [Add Python to System Path](#add-python-to-system-path-)
    - [For Windows 10 (showing a listbox dialog)](#for-windows-10-showing-a-listbox-dialog-)
    - [For Windows 7 or before (showing a textbox dialog)](#for-windows-7-or-before-showing-a-textbox-dialog-)
  - [Verify if Python can be run from command](#verify-if-python-can-be-run-from-command-)
  - [Verify if pip can be run from command](#verify-if-pip-can-be-run-from-command-)
  - [Install the required packages](#install-the-required-packages-)
  - [Start deresute-tools](#start-deresute-tools-)
- [Troubleshooting](#troubleshooting-)
  - [Qt5 error message / GUI issues](#qt5-error-message-is-shown--the-interface-looks-like-windows-xp--icons-thumbnails-are-not-shown-)
  - [Mistakenly overwritten the PATH environment variable](#if-you-have-mistakenly-overwritten-the-path-environment-variable-value-instead-of-appending-the-new-path-at-the-end-)
  - [sqlite3.OperationalError: table ... has no column named ...](#receiving-sqlite3operationalerror-table--has-no-column-named--)

## Setup [^](#table-of-contents)

_For those who are not able to use the release directly, or wish to modify the tool._

### Download the source code from the Download ZIP button. [^](#table-of-contents)

(If you know about version control using git / Github Desktop / etc., you can clone the repository instead.)

### Install Python [^](#table-of-contents)

The compiled release comes with the Python interpreter and the required libraries, which you need to install manually if you are using the source code.

If you do not have Python installed, please visit [Python](https://www.python.org/downloads/) to find the suitable version.

#### Extra Note for Windows 7: [^](#table-of-contents)
- For last release version of Python 3 supported, please refer to:
  - [Python 3.8.10](https://www.python.org/downloads/release/python-3810/)
  - [Python 3.7.9](https://www.python.org/downloads/release/python-379/)

Download the Windows installer and follow the instructions to install.
- (Please notice that the installer is using **.exe** extension downloaded from the link at the first column, not the .asc file (GPG signature from SIG) for integrity check at the last column)
- (Check the "Add <ins>P</ins>ython 3.\_ to PATH", then you can skip the next part.)

### Add Python to System Path [^](#table-of-contents)

***(Skip this part if "Add <ins>P</ins>ython 3.\_ to PATH" option was checked when installing Python.)***

Press \[Win\]+R, and type `systempropertiesadvanced` to open the System Properties setting dialog.

Choose the Advanced Tag, and then click the Environment Variables button at the bottom.

Find the "Path" variable in the System variables list, then click Edit.

#### For Windows 10 (showing a listbox dialog) [^](#table-of-contents)

Click New, then input `C:\Users\User\AppData\Local\Programs\Python\Python37`.
- (Please change it to the actual installation path of Python, where `User` refer to the user name, and `Python37` refer to the installed Python version)
- Better add `C:\Users\User\AppData\Local\Programs\Python\Python37\Scripts` also.

#### For Windows 7 or before (showing a textbox dialog) [^](#table-of-contents)

**Please follow carefully to avoid overwriting the old environment variable entries**

If the value field does not end with a semicolon (`;`), add it to the end, followed by `C:\Users\User\AppData\Local\Programs\Python\Python37;`.
- (Please change it to the actual installation path of Python, where `User` refer to the user name, and `Python37` refer to the installed Python version)
- (i.e. If the original Path value is `C:\WINDOWS\system32;C:\WINDOWS`, change it to `C:\WINDOWS\system32;C:\WINDOWS;C:\Users\User\AppData\Local\Programs\Python\Python37;`)
  - Notice that the original value is still there.

After adding, press \[Win\]+R, and type `cmd` to start the Command Prompt.

Type `echo %PATH%` after `>`, then press \[Enter\], the content of the Path variable (from both User and System) will be printed.

- Check if Python's path is listed there. (Supposed to be at the end if it is just added at the end.)

### Verify if Python can be run from command [^](#table-of-contents)

Type `python` in the Command Prompt, then press \[Enter\] to see if `Python` is launched.

(If you see something like `python is not recognized as an internal command`, please check whether you have installed Python or added Python to the system PATH successfully.)

Type `exit()` after `>>> ` to leave the Python shell.

### Verify if pip can be run from command [^](#table-of-contents)

Type `pip` in the Command Prompt, then press \[Enter\] to see if `pip` is launched.

(If you have multiple Python installed on the same device, you can use `python -m pip` instead. (change `python` to the path of the python executable if it is not the default))

If `pip` is not installed, you may need to install it via `python -m ensurepip --upgrade`.

- If it is not working, check [the official documentation](https://pip.pypa.io/en/stable/installation/) for further guidance or troubleshooting.

### Install the required packages [^](#table-of-contents)

*If you have other packages installed and may lead to conflicts, you may consider running the following steps via the (virtualenv)[https://docs.python.org/3/library/venv.html].*

Type `cd C:\...\...` in the command prompt, where `C:\...\...` is where the download zip is extracted to (where `C:\...\...\requirements.txt` is located), then press \[Enter\].

Type `python -m pip install -r requirements.txt`, then press \[Enter\], the pip will install the packages stated in `requirements.txt`. Please be patient.

### Start deresute-tools [^](#table-of-contents)

*Make sure that you are still in `C:\...\...` for the command prompt, make sure that `chihiro.py` is there.*

Type `python chihiro.py`, then press \[Enter\]. If there are no issues, then the tool would start peacefully.

If it does not start, please refer to the troubleshooting section.

To start the tool more efficiently without using command prompt later on, you can create a `cmd` or `bat` file at the directory where `chihiro.py` is located, with the below text:

```
python chihiro.py
```

(which is the `run_default.bat` in the forked repo.)

Later you can double click this file to start the tool without typing in the command prompt.

## Troubleshooting [^](#table-of-contents)

Here some issues encountered by others when trying to start the tool are listed.

### Qt5 error message is shown / The interface looks like Windows XP / Icons (Thumbnails) are not shown [^](#table-of-contents)

For the first case, the line before the tool is terminated should be something like the following:

```
qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.
```

This is usually due to that Qt5 cannot detect the Vista style installed from the `PyQt5` package.

You may try to add the system variable to let Qt5 know about the location of `qwindowsvistastyle.dll`.

From the environment variables dialog, press New to create a new entry.

**Variable name:** `QT_QPA_PLATFORM_PLUGIN_PATH`

**Variable value:** `C:\Users\User\AppData\Local\Programs\Python\Python37\Lib\site-packages\PyQt5\Qt5\plugins\styles`

(where `User` is the username, `Python37` is the installed Python version, please check if the path exists before setting the environment variable.)

Try to start the tool again.

### If you have mistakenly overwritten the PATH environment variable value instead of appending the new path at the end [^](#table-of-contents)

*(Make sure that you have not yet restarted the computer, otherwise this no longer helps)*

Press \[Win\]+R, and type `regedit` to open the registry editor.

Type `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment` in the address bar, click \[Enter\].

Check the value of the **Path** entry. If it is the original one, then double click the entry, copy the value, then follow the `Add Python to System Path` part and paste the value back to the Path Variable to proceed.

If this **Path** entry is corrupted, you may need to check the below paths instead:

- `HKLM\SYSTEM\ControlSet001\Control\Session Manager\Environment`

- `HKLM\SYSTEM\ControlSet002\Control\Session Manager\Environment`

- `...`

### Receiving "sqlite3.OperationalError: table ... has no column named ..." [^](#table-of-contents)

There may be a breaking change in the database.

You may try to remove `chihiro.db` under `data/db` before retrying to see if the problem is resolved.

### TypeError: Cannot cast scalar from dtype('int64') to dtype('int32') according to the rule 'safe'

You may be running 32-bit Python which numpy shows some problems on that.

You can use 64-bit Python, or revert the changes in `src\network\chart_cache_updater.py` done by Smanmos manually (Notice that without vectorization the code may run slower):

```
- from logic.live import classify_note_vectorized
+ from logic.live import classify_note
- notes_data['note_type'] = classify_note_vectorized(notes_data)
+ notes_data['note_type'] = notes_data.apply(classify_note, axis=1)
```


