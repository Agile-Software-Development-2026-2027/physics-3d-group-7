"""Avvio: python -m ApKit4D [file.czi] [--software-gl]"""

import argparse
import os


def main():
    ap = argparse.ArgumentParser(description="ApKit4D — preprocessing, blob finder e tracking su stack lightfield")
    ap.add_argument("czi", nargs="?", default=None, help="file .czi da aprire subito")
    ap.add_argument("--diagnostica", action="store_true",
                    help="registra in ApKit4D_blocchi.log ogni volta che l'interfaccia resta "
                         "bloccata piu' di un secondo, con la riga di codice responsabile")
    ap.add_argument("--software-gl", action="store_true",
                    help="OpenGL software (Mesa llvmpipe) invece della GPU: serve quando il driver "
                         "NVIDIA non crea contesti (es. 'Driver/library version mismatch' dopo un "
                         "aggiornamento senza riavvio). Piu' lento nel 3D, ma funziona.")
    a = ap.parse_args()
    if a.software_gl:
        # va impostato prima che Qt/vispy carichino libGL
        os.environ["__GLX_VENDOR_LIBRARY_NAME"] = "mesa"
        os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"

    import napari
    from ApKit4D.compat import applica_patch_napari
    from ApKit4D.gui import LightfieldApp

    for nome in applica_patch_napari():
        print(f"correzione napari applicata: {nome}")

    viewer = napari.Viewer(title="ApKit4D — BIOLIGHT")
    viewer._apkit4d = LightfieldApp(viewer, a.czi)  # riferimento: evita la garbage collection

    # A schermo intero. Un solo showMaximized() non basta: napari ripristina la geometria
    # salvata nelle sue impostazioni subito dopo, e la finestra torna a meta' schermo.
    # Quindi si forza prima la geometria dello schermo, poi si ripete a impaginazione finita.
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication
    w = viewer.window._qt_window
    schermo = QApplication.primaryScreen().availableGeometry()
    w.setGeometry(schermo)
    w.showMaximized()
    QTimer.singleShot(0, w.showMaximized)
    QTimer.singleShot(400, w.showMaximized)
    viewer._apkit4d.raise_file_panel()

    if a.diagnostica:
        from pathlib import Path
        from ApKit4D.watchdog import Sorvegliante
        log = Path(__file__).resolve().parent.parent / "ApKit4D_blocchi.log"
        viewer._sorvegliante = Sorvegliante(log)
        print(f"diagnostica attiva: i blocchi oltre 1 s finiscono in {log}")

    napari.run()


if __name__ == "__main__":
    main()
