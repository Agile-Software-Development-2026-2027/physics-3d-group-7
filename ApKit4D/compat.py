"""
compat.py
=========
Correzioni applicate a napari a runtime, per difetti suoi che si manifestano in questa app.

Ogni voce qui dentro va trattata come temporanea: vale per la versione di napari installata
(0.7.0) e andra' tolta quando il difetto sara' corretto a monte.

1. Raggio quasi parallelo a una faccia del volume (in vista 3D)
   `Layer._get_ray_intersections` si protegge solo dal caso in cui NESSUNA faccia del
   volume venga intersecata:

       if front_face_normal is None and back_face_normal is None:
           return None, None

   ma quando il raggio dello sguardo e' quasi parallelo a una faccia puo' capitare che
   ne risulti intersecata una sola. L'altra resta None e finisce in
   `face_coordinate_from_bounding_box`, che fa `face_normal[axis]` e solleva
   `TypeError: 'NoneType' object is not subscriptable`.

   Verificato con i valori di un caso reale (volume 95x512x512, cursore sul bordo z=0,
   direzione dello sguardo con componente z di 7e-4): faccia anteriore None, posteriore
   [-1, 0, 0].

   Succede mentre si ruota il volume in 3D, perche' il controllo di stato di napari gira a
   ogni movimento del mouse e interroga il livello attivo. Non fa cadere l'app, ma riempie
   lo schermo di notifiche di errore.
"""

import numpy as np


def applica_patch_napari():
    """Applica le correzioni. Ritorna l'elenco di quelle effettivamente applicate."""
    applicate = []

    from napari.layers.base import base

    if not getattr(base.Layer._get_ray_intersections, "_apkit4d_patch", False):
        originale = base.Layer._get_ray_intersections

        def _get_ray_intersections(self, position, view_direction, dims_displayed,
                                   world=True, bounding_box=None):
            try:
                return originale(self, position, view_direction, dims_displayed,
                                 world=world, bounding_box=bounding_box)
            except TypeError:
                # una sola faccia intersecata: per napari equivale a "il raggio non
                # attraversa il volume", che e' gia' un caso previsto
                return None, None

        _get_ray_intersections._apkit4d_patch = True
        base.Layer._get_ray_intersections = _get_ray_intersections
        applicate.append("raggio quasi parallelo a una faccia (vista 3D)")

    return applicate


def verifica_patch():
    """Riproduce il caso che falliva, per controllare che la correzione tenga."""
    from napari.utils.geometry import find_front_back_face
    pos = np.array([8.31116e-02, 4.23872e+02, 3.56363e+02])
    direzione = np.array([7.15412e-04, 5.19325e-01, -8.54577e-01])
    bbox = np.array([[0.0, 95.0], [0.0, 512.0], [0.0, 512.0]])
    anteriore, posteriore = find_front_back_face(pos, bbox, direzione)
    return (anteriore is None) != (posteriore is None)   # True = il caso limite esiste
