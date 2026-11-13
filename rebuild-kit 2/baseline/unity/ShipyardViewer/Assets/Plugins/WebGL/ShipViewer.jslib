mergeInto(LibraryManager.library, {
  ShipViewer_NotifyReady: function () {
    try {
      if (Module.canvas) Module.canvas.dispatchEvent(new CustomEvent('shipviewer-ready'));
    } catch (e) {}
  },
  ShipViewer_FleetEvent: function (slot, selected) {
    if (Module.canvas) {
      Module.canvas.dispatchEvent(new CustomEvent(selected ? 'shipyard-select' : 'shipyard-hover', { detail: slot }));
    }
  },
  ShipViewer_NotifyHover: function (active) {
    if (Module.canvas) {
      Module.canvas.dispatchEvent(new CustomEvent('shipviewer-hover', { detail: Boolean(active) }));
    }
  }
});
