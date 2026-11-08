mergeInto(LibraryManager.library, {
  ShipViewer_NotifyReady: function () {
    try {
      if (Module.canvas) Module.canvas.dispatchEvent(new CustomEvent('shipviewer-ready'));
    } catch (e) {}
  }
});
