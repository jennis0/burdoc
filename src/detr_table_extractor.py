
from transformers import DetrFeatureExtractor, TableTransformerForObjectDetection
from PIL import Image
import PIL.ImageOps as imops
import torch
from logging import Logger
from typing import Any, List
import plotly.express as plt
import PIL.ImageStat as imstat
import math

from .layout_objects import LBlock

class DetrTableExtractor(object):

    def __init__(self, logger: Logger):
        self.logger = logger.getChild('tableextractor')
        self.margin = 25
        self.threshold = 0.95
        self.extractor = DetrFeatureExtractor()
        self.detector_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-detection')
        self.structure_model = TableTransformerForObjectDetection.from_pretrained('microsoft/table-transformer-structure-recognition')


    def _preprocess_image(self, page_image: Image.Image):
        image = page_image.convert('RGB')
        width, height = image.size
        image.resize((min(int(width), 800), min(int(height),1333)))

        stats = imstat.Stat(image)
        r,g,b = stats.rms
        brightness = math.sqrt(0.241*(r**2) + 0.691*(g**2) + 0.068*(b*2))
        if brightness < 100:
            self.logger.debug("Inverting image colours")
            image = imops.invert(image)

        encoding = self.extractor(image, return_tensors='pt')
        return encoding

    def _do_extraction(self, model, image: Image.Image):
        features = self._preprocess_image(image)
        with torch.no_grad():
            outputs = model(**features)
        width, height = image.size
        return self.extractor.post_process_object_detection(outputs, threshold=0.7, target_sizes=[(height, width)])[0]


    def extract_tables(self, page_image: Image.Image, _: List[LBlock]) -> List[Any]:
        results = self._do_extraction(self.detector_model, page_image)
        self.logger.debug(f"Found {len(results['boxes'])} tables{' at:' if len(results['boxes']) > 0 else ''}")
        for s,b in zip(results['scores'], results['boxes']):
            self.logger.debug(f"Bbox={b} Score={s}")

        self.plot_tables(page_image, results['scores'], results['labels'], results['boxes'])

        tables = []
        if len(results['boxes']) > 0:
            for s,b in zip(results['scores'], results['boxes']):
                if s < self.threshold:
                    continue
                crop_box = [
                    max(0, int(b[0].item()-self.margin)),
                    max(0, int(b[1].item()-self.margin)),
                    min(page_image.size[0], int(b[2].item()+self.margin)),
                    min(page_image.size[1], int(b[3].item()+self.margin)),

                ]
                table_image = page_image.crop(crop_box)
                tables.append(self._do_extraction(self.structure_model, table_image))
                #self.plot_tables(table_image, results['scores'], results['labels'], results['boxes'])

        return tables

    def plot_tables(self, page_image, scores, labels, boxes):
        
        colors=[
            'Grey',
            'RoyalBlue',
            'Crimson',
            'Green',
            'Purple',
            'Orange',            
        ]
        fig = plt.imshow(page_image)
        ls = [[l,self.structure_model.config.id2label[l]] for l in set(labels.tolist())]
        cols = [colors[l[0]] for l in ls]
        print(ls, cols)
        for score, label, (xmin, ymin, xmax, ymax)  in zip(scores.tolist(), labels.tolist(), boxes.tolist()):
            fig.add_shape(dict(
                type='rect',
                xref='x',
                yref='y',
                x0=xmin, y0=ymin, x1=xmax, y1=ymax,
                opacity=0.6,
                line=dict(color=colors[label], width=3)))
            fig.add_annotation(text=f'{self.structure_model.config.id2label[label]}: {score:0.2f}', x=xmin+1, y=ymin+1)
        
        for l,c in zip(ls, cols):
            fig.add_scatter(x=[None], y=[None], name=l[1], line=dict(width=3, color=c))
        
        fig.update_layout({'showlegend': True, 'height':1000, 'xaxis':{'showticklabels':False}, 'yaxis':{'showticklabels':False}})
        fig.show()
     
