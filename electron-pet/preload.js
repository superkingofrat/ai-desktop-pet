const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getPetPosition: () => ipcRenderer.invoke("get-pet-position"),
  toggleChat: () => ipcRenderer.invoke("toggle-chat"),
  closeChat: () => ipcRenderer.invoke("close-chat"),
  movePet: (dx, dy) => ipcRenderer.invoke("move-pet", dx, dy),
  setPetPosition: (x, y) => ipcRenderer.invoke("set-pet-position", x, y),
});
