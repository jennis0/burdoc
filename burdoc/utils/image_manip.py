from typing import List, Tuple

import numpy as np
import scipy
import scipy.cluster
import scipy.misc
from PIL.Image import Image
from PIL.ImageFilter import GaussianBlur


def get_image_palette(im: Image, n_colours: int, n_means: int=5) -> List[Tuple[float, float, float]]:
    im = im.resize((150, 150))      # optional, to reduce time
    gb = GaussianBlur(radius=3)
    im = im.filter(gb)
    ar = np.asarray(im)
    shape = ar.shape
    ar = ar.reshape(scipy.product(shape[:2]), shape[2]).astype(float)
    
    codes, _ = scipy.cluster.vq.kmeans(ar, 5)
    vecs, _ = scipy.cluster.vq.vq(ar, codes)         # assign codes
    counts, _ = scipy.histogram(vecs, len(codes))    # count occurrences

    s = 150*150
    code_counts = [([round(c, 0) for c in code[:3]], round(count / s, 2)) for code, count in zip(codes, counts)]
    code_counts.sort(key=lambda x: x[1], reverse=True)
    return code_counts[:n_colours]