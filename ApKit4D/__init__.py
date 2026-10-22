"""
ApKit4D — app napari per preprocessing e blob finding su stack lightfield 4D.

Moduli:
    io_czi      lettura lazy dei .czi (un volume alla volta) + metadati fisici
    preprocess  crop ROI, denoise, sottrazione fondo, finestra/gamma/log/CLAHE
    blobfinder  detection 3D alla "Blob Finder": semi LoG + watershed
    params      persistenza dei parametri per file
    batch       esecuzione a riga di comando su un intervallo di frame
    gui         l'app napari (python -m ApKit4D)
"""
