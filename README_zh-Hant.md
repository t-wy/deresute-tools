# Deresute Tools

你可以從[主分支](https://github.com/deresute-tools/deresute-tools)取得專為 Windows 10 而編譯的軟體。(可能未包含最新功能)

[官方說明書 (英文)](https://docs.google.com/document/d/e/2PACX-1vTjhwFyOT-pawJiBWhRjg9Edvx0AVcx1Dy-qw5QpNKG3HJhn2LuEl42dAxUVPaimv4O7xfJ1WFXTyz2/pub)

## 語言 (Languages):

- [英文 (English)](README.md)
- [正體中文 (Trad. Chinese)](README_zh-Hant.md)

## 目錄
- [安裝及設定](#安裝及設定-)
  - [從 Download ZIP 按鈕下載原始碼](#從-download-zip-按鈕下載原始碼-)
  - [安裝 Python](#安裝-python-)
    - [關於 Windows 7 的額外指引](#關於-windows-7-的額外指引-)
  - [把 Python 加入系統環境變數](#把-python-加入系統環境變數-)
    - [Windows 10 或以後的使用者（編輯時顯示列表的）](#windows-10-或以後的使用者編輯時顯示列表的-)
    - [Windows 7 或以前的使用者（編輯時顯示文字編輯方格的）](#windows-7-或以前的使用者編輯時顯示文字編輯方格的-)
  - [檢查 Python 能否從命令提示字元執行](#檢查-python-能否從命令提示字元執行-)
  - [檢查 pip 能否從命令提示字元執行](#檢查-pip-能否從命令提示字元執行-)
  - [安裝所需套件](#安裝所需套件-)
  - [啟動 deresute-tools](#啟動-deresute-tools-)
- [疑難排解](#疑難排解-)
  - [Qt5 錯誤訊息 / 介面問題](#看到關於-qt5-的錯誤訊息--介面看起來像-windows-xp--偶像的圖示沒有如常顯示-)
  - [錯誤覆寫了 PATH 變數的內容](#如果你不小心覆寫了-path-變數的內容而不是把路徑加在-path-的最後方-)
  - [sqlite3.OperationalError: table ... has no column named ...](#看到-sqlite3operationalerror-table--has-no-column-named--)
  - [TypeError: cast from dtype('int64') to dtype('int32')](#typeerror-cannot-cast-scalar-from-dtypeint64-to-dtypeint32-according-to-the-rule-safe-)

## 安裝及設定 [^](#目錄)

_當發布版本無法正常執行，或需要手動更改軟體功能時可參閱_

### 從 Download ZIP 按鈕下載原始碼 [^](#目錄)

（如果你知道如何使用 git / Github 桌面版等工具進行版本控制，你可以直接 Clone 這個 Repo）

### 安裝 Python [^](#目錄)

編譯版本已經包含 Python 直譯器及所需的函式庫。如果你直接使用原始碼開啟軟體，你需要先行安裝所需內容。

如果你的裝置還沒有安裝 Python，請到 [Python 官方網站](https://www.python.org/downloads/) 尋找適合的版本下載。

#### 關於 Windows 7 的額外指引 [^](#目錄)
- 對於 Python 3 最後支援此作業系統的版本，請查閱：
  - [Python 3.8.10](https://www.python.org/downloads/release/python-3810/)
  - [Python 3.7.9](https://www.python.org/downloads/release/python-379/)

下載 Windows 版的安裝器並根據指示安裝。
- （請注意安裝器是第一行 **.exe** 副檔名的檔案，而非最後一行的檢查完整性用的 .asc 檔案（ GPG 簽署））
- （如果有勾選 "Add <ins>P</ins>ython 3.\_ to PATH"（把 Python 3.\_ 加入環境變數）可以跳過下一步）(Check the , then you can skip the next part.)

### 把 Python 加入系統環境變數 [^](#目錄)

***（如果你有勾選 "Add <ins>P</ins>ython 3.\_ to PATH"（把 Python 3.\_ 加入環境變數）可以略過此步驟）***

用鍵盤按 \[Win\]+R，然後輸入 `systempropertiesadvanced`　以開啟系統內容設定方塊。

選擇進階分頁，然後點擊底部的「環境變數」按鈕。

在系統變數列表尋找並點選名為「Path」的變數，然後按編輯。

#### Windows 10 或以後的使用者（編輯時顯示列表的） [^](#目錄)

按「新增」，然後輸入 `C:\Users\User\AppData\Local\Programs\Python\Python37`。
- （請將其改為實際安裝 Python 的路徑，即把 `User` 改成用戶名稱，`Python37` 改成實際安裝的 Python 版本）
- （最好把 `C:\Users\User\AppData\Local\Programs\Python\Python37\Scripts` 也加進去。）
- (如果 Python 是為所有使用者安裝的，此路徑可能類似 `C:\Program Files\Python37\` 而不是 `C:\Users\User\AppData\Local\Programs\Python\Python37`。)

#### Windows 7 或以前的使用者（編輯時顯示文字編輯方格的） [^](#目錄)

**請小心跟從指示，以免覆蓋原有的環境變數內容**

如果目前的值不是以分號（`;`）作結，請把分號加在結尾，然後再輸入`C:\Users\User\AppData\Local\Programs\Python\Python37;`。
- （請將其改為實際安裝 Python 的路徑，即把 `User` 改成用戶名稱，`Python37` 改成實際安裝的 Python 版本）
- （例：如果本來 `Path` 的值為 `C:\WINDOWS\system32;C:\WINDOWS`，請將其改為 `C:\WINDOWS\system32;C:\WINDOWS;C:\Users\User\AppData\Local\Programs\Python\Python37;`）
  - 注意原有的值應該還在。
- (如果 Python 是為所有使用者安裝的，此路徑可能類似 `C:\Program Files\Python37\` 而不是 `C:\Users\User\AppData\Local\Programs\Python\Python37`。)

加入之後，用鍵盤按 \[Win\]+R，然後輸入 `cmd` 開啟命令提示字元。

在 `>` 右方輸入 `echo %PATH%` 然後按 \[Enter\]，Path 變數的內容（包括用戶變數及系統變數）應該會顯示。

- 檢查 Python 的路徑是否有被包含在內。（如果是剛按指示加入的應該相關路徑會在結尾顯示）

### 檢查 Python 能否從命令提示字元執行 [^](#目錄)

在命令提示字元輸入 `python`，然後按 \[Enter\] 檢查 `Python` 有否正常啟動。

（如果你看見類似 `'python' 不是內部或外部命令、可執行的程式或批次檔。` 的文字，請檢查你是否有正常安裝 Python 且將其加入系統 Path 變數。）

在 `>>> ` 右方輸入 `exit()` 以關閉 Python。

### 檢查 pip 能否從命令提示字元執行 [^](#目錄)

在命令提示字元輸入 `pip`，然後按 \[Enter\] 檢查 `pip` 有否正常啟動。

（如果你的裝置有安裝多於一個 Python，你可以使用 `python -m pip`。（如果 `python` 啟動的不是預設的 python 版本，請將上述指令的 `python` 改成 python 的路徑））

如果 `pip` 未被安裝，你需要使用 `python -m ensurepip --upgrade` 安裝 `pip`。

- 如果這指令不能正常運作，請檢查 [官方文件](https://pip.pypa.io/en/stable/installation/) 關於其他指引或疑難排解。

### 安裝所需套件 [^](#目錄)

*如果你已安裝其他或會構成衝突的套件，你可以考慮從 [virtualenv](https://docs.python.org/3/library/venv.html) 執行下列步驟*

在命令提示字元輸入 `cd C:\...\...`（當中的 `C:\...\...` 指下載的壓縮檔解壓縮的位置，`C:\...\...\requirements.txt` 應該在該資料夾內），然後按 \[Enter\]，

輸入 `python -m pip install -r requirements.txt`，然後按 \[Enter\]，pip 會安裝 `requirements.txt` 裡提及的所有套件。請耐心等待。

### 啟動 deresute-tools [^](#目錄)

*請確定命令提示字元的路徑還在  `C:\...\...`，並確定 `chihiro.py` 在內。*

輸入 `python chihiro.py`，然後按 \[Enter\]。如果沒有問題，此工具將會正常啟動。

如無法正常啟動，請參考下方的疑難排解部分。

在日後若要跳過開啟命令提示字元的步驟更方便地啟動工具，你可以在 `chihiro.py` 所在的資料夾創建一個有以下內容 `cmd` or `bat` 的文件：

```
python chihiro.py
```

（跟本 Repo `run_default.bat` 的內容一樣）

日後你可以雙擊此檔案無須使用命令提示字元直接啟動工具。

## 疑難排解 [^](#目錄)

以下是其他人嘗試啟動工具時曾經面對的問題。

### 看到關於 Qt5 的錯誤訊息 / 介面看起來像 Windows XP / 偶像的圖示沒有如常顯示 [^](#目錄)

關於第一個情況，在工具閃退前的那一行應該會顯示類似如下內容：

```
qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.
```

這一般是因為 Qt5 無法偵測 `PyQt5` 套件內安裝的 Vista 風格。

你可以嘗試新增系統變數以讓 Qt5 知道 `qwindowsvistastyle.dll` 的位置。

從環境變數的方塊，按新增以建立一個新的變數。

**變數名稱：** `QT_QPA_PLATFORM_PLUGIN_PATH`

**變數值：** `C:\Users\User\AppData\Local\Programs\Python\Python37\Lib\site-packages\PyQt5\Qt5\plugins\styles`

（把 `User` 改成用戶名稱, `Python37` 改成所安裝的 Python 版本，請在設定環境變數前檢查路徑是否存在。）

再重試開啟工具。

### 如果你不小心覆寫了 PATH 變數的內容，而不是把路徑加在 PATH 的最後方 [^](#目錄)

*（請確定你的電腦還沒有重新開機，否則此方法不再有效）*

用鍵盤輸入 \[Win\]+R，然後輸入 `regedit` 以開啟登錄編輯程式。

在路徑列輸入 `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment`，然後按 \[Enter\]。

檢查名稱下 **Path** 的內容。如果還是原有的內容，請雙擊有關列，複製其數值，然後根據 `把 Python 加入系統環境變數` 部分的指示貼上此數值到 Path 變數以繼續。

如果此  **Path** 的內容已經被破壞，你或需要使用以下的路徑 **Path** 的內容進行還原：

- `HKLM\SYSTEM\ControlSet001\Control\Session Manager\Environment`

- `HKLM\SYSTEM\ControlSet002\Control\Session Manager\Environment`

- `...`

### 看到 "sqlite3.OperationalError: table ... has no column named ..." [^](#目錄)

要更新工具版本跟原有版本之間可能有資料庫欄位的變更。

你可以先刪除 `data/db` 下的 `chihiro.db`，再重試以檢查問題是否被解決。

### TypeError: Cannot cast scalar from dtype('int64') to dtype('int32') according to the rule 'safe' [^](#目錄)

更新：目前版本應該沒有此問題，請下載最新版本。

如果你使用的是 32 位元組的 Python，numpy 套件在計算的時候可能會出現有關問題。

你可以改用 64 位元組的 Python，或者取消 Smanmos 在 `src\network\chart_cache_updater.py` 裡作出的變更（注意刪除向量化後工具載入所需時間可能會增加）

```
- from logic.live import classify_note_vectorized
+ from logic.live import classify_note
- notes_data['note_type'] = classify_note_vectorized(notes_data)
+ notes_data['note_type'] = notes_data.apply(classify_note, axis=1)
```


