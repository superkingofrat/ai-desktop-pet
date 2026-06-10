const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const fs = require("fs");
const path = require("path");

let petWindow = null;
let chatWindow = null;

function createPetWindow() {
  petWindow = new BrowserWindow({
    width: 100,
    height: 100,
    x: 0,
    y: 0,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  petWindow.loadFile("renderer.html");
  petWindow.setVisibleOnAllWorkspaces(true);

  // Reposition to bottom-right after window is ready
  petWindow.once("ready-to-show", () => {
    const { screen } = require("electron");
    const displays = screen.getPrimaryDisplay();
    const { width, height } = displays.workAreaSize;
    const [winW, winH] = petWindow.getSize();
    petWindow.setPosition(width - winW - 20, height - winH - 20);
  });

  petWindow.on("closed", () => {
    petWindow = null;
    if (chatWindow) {
      chatWindow.close();
      chatWindow = null;
    }
  });
}

function createChatWindow(parentX, parentY) {
  if (chatWindow) {
    chatWindow.show();
    chatWindow.focus();
    return;
  }

  chatWindow = new BrowserWindow({
    width: 340,
    height: 440,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    parent: petWindow,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Position chat to the left of the pet
  const chatX = parentX - 340 + 20;
  const chatY = Math.max(0, parentY - 440 + 60);
  chatWindow.setPosition(Math.max(0, chatX), chatY);
  chatWindow.loadFile("renderer.html", { hash: "chat" });

  chatWindow.on("closed", () => {
    chatWindow = null;
  });
}

// IPC: get pet window position
ipcMain.handle("get-pet-position", () => {
  if (!petWindow) return { x: 0, y: 0 };
  const [x, y] = petWindow.getPosition();
  return { x, y };
});

// IPC: toggle chat window
ipcMain.handle("toggle-chat", () => {
  if (!petWindow) return;
  const [px, py] = petWindow.getPosition();
  if (chatWindow && !chatWindow.isDestroyed()) {
    chatWindow.close();
    chatWindow = null;
  } else {
    createChatWindow(px, py);
  }
});

// IPC: close chat window
ipcMain.handle("close-chat", () => {
  if (chatWindow && !chatWindow.isDestroyed()) {
    chatWindow.close();
    chatWindow = null;
  }
});

// IPC: move pet window
ipcMain.handle("move-pet", (_, dx, dy) => {
  if (!petWindow) return;
  const [x, y] = petWindow.getPosition();
  petWindow.setPosition(x + dx, y + dy);
});

// IPC: set pet position
ipcMain.handle("set-pet-position", (_, x, y) => {
  if (!petWindow) return;
  petWindow.setPosition(x, y);
});



// IPC: select and read an image file
ipcMain.handle("select-image-file", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [{ name: "Images", extensions: ["jpg", "jpeg", "png", "gif", "webp", "bmp"] }],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  const filePath = result.filePaths[0];
  const ext = path.extname(filePath).slice(1).toLowerCase();
  const mimeMap = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif", webp: "image/webp", bmp: "image/bmp" };
  const mime = mimeMap[ext] || "image/png";
  const buffer = fs.readFileSync(filePath);
  const b64 = buffer.toString("base64");
  return { path: filePath, dataUrl: `data:${mime};base64,${b64}` };
});


// IPC: update pet window settings (image, name) from chat
ipcMain.handle("update-pet-settings", () => {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.executeJavaScript(`
      var img = localStorage.getItem("pet_image");
      var name = localStorage.getItem("pet_name");
      var pe = document.getElementById("petEmoji");
      var pc = document.getElementById("petCustomImage");
      var pa = document.getElementById("petAvatar");
      if (img && img.startsWith("data:")) {
        if (pe) pe.style.display = "none";
        if (pc) { pc.style.display = "inline"; pc.src = img; }
        if (pa) pa.classList.add("has-image");
      } else {
        if (pe) pe.style.display = "inline";
        if (pc) pc.style.display = "none";
        if (pa) pa.classList.remove("has-image");
      }
    `);
  }
});

app.whenReady().then(createPetWindow);

app.on("window-all-closed", () => {
  app.quit();
});

