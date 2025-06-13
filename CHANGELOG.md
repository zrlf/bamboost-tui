## 0.2.0 (2025-06-13)

### Feat

- introduce mappable keys
- set up command registry for commands callable via keybind and from palette

### Refactor

- improve command and keymap feature
- introduce command palette for all key bindings instead of manual commands

## 0.1.0 (2025-05-29)

### Feat

- **commands**: add support for custom command palette
- add keybind to open directory in vim
- keybind to sync collection
- system command to scan for collections
- keybind to reload collection data
- remote collection picker
- add delete simulation logic
- make command line a widget instead of a screen
- improve keybindings
- update styling (mainly in css file), make widget mixin for keychains (KeySubgrouppsMixin)
- **hdfview**: finalize hdfview for now
- **hdfview**: add mouse hover and click
- hdf viewer static list and preview, focus border color
- hdf viewer
- active tab fixed
- tabs and cycle
- single screen for collection, update table widget when choosing, adding tabs
- collection table header
- remove welcome screen in favor of an empty collection table
- when completing, add space after
- collection picker <ctrl+m>
- process spinner for scan_paths
- edited autocomplete from darren for my use case, with dropdown on top
- commandline goto function works (proof of concept)
- provide cell highlighting function

### Fix

- **app**: fix screen query (change in textual 3.0.0)
- subgroup mixin for widgets, use run_action
- import path
- **commandline**: improved structure, fixed previous issues
- **hdfview**: scrollable container for attrsview table
- horizontal scroll
- refresh of headers on horizontal scroll

### Refactor

- reorganize modules
- structure modules
