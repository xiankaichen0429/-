const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  },
  selectFiles: () => ipcRenderer.invoke('select-paper-files'),
  extractMetadata: (filePath) => ipcRenderer.invoke('extract-paper-metadata', filePath)
})
