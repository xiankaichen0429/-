const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron')
const { spawn } = require('child_process')
const path = require('path')

function getExtractorScript() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'extract.py')
  }
  return path.join(__dirname, '..', 'backend', 'extract.py')
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    title: '个人论文文献管理工具',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (!app.isPackaged) {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

ipcMain.handle('select-paper-files', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择论文文件',
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: '论文文件', extensions: ['pdf', 'docx'] }
    ]
  })

  return result.canceled ? [] : result.filePaths
})

ipcMain.handle('extract-paper-metadata', async (_event, filePath) => {
  const script = getExtractorScript()

  return new Promise((resolve, reject) => {
    const child = spawn('python', ['-X', 'utf8', script, filePath], {
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1'
      }
    })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString()
    })

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString()
    })

    child.on('error', reject)

    child.on('close', (code) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(stdout))
        } catch {
          reject(new Error('无法解析识别结果'))
        }
      } else {
        reject(new Error(stderr || `识别进程退出码：${code}`))
      }
    })
  })
})

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
