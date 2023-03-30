from typing import Any, List, Tuple

import numpy as np
import scipy
import scipy.cluster
import scipy.misc
from PIL.Image import Image
from PIL.ImageFilter import GaussianBlur


def get_image_palette(image: Image, n_colours: int, n_means: int=5) -> List[Tuple[List[float], Any]]:
    image = image.resize((150, 150))      # optional, to reduce time
    blur = GaussianBlur(radius=3)
    image = image.filter(blur)
    arr = np.asarray(image)
    shape = arr.shape
    if len(shape) == 3:
        arr = arr.reshape(scipy.product(shape[:2]), shape[2]).astype(float)
        n_dims = 3
    else:
        arr = arr.reshape(scipy.product(shape[:2]), 1).astype(float)
        n_dims = 2
    
    codes, _ = scipy.cluster.vq.kmeans(arr, n_means)
    vecs, _ = scipy.cluster.vq.vq(arr, codes)         # assign codes
    counts, _ = scipy.histogram(vecs, len(codes))    # count occurrences

    pixel_count = 150*150
    code_counts = [([round(c, 0) for c in code[:n_dims]], round(count / pixel_count, 2)) for code, count in zip(codes, counts)]
    code_counts.sort(key=lambda x: x[1], reverse=True)
    return code_counts[:n_colours]