import argparse
import glob
import os
import re
import torch
import subprocess
import crnn.utils as utils
import crnn.dataset as dataset
import random

from pathlib import Path
from difflib import SequenceMatcher
from torch.autograd import Variable
from PIL import Image, ImageDraw, ImageFont
from crnn.models.crnn import CRNN
from collections import Counter


YOLO_FOLDER = os.path.join(os.path.dirname(__file__), "yolo")
CRNN_FOLDER = os.path.join(os.path.dirname(__file__), "crnn")
BRAND_FILE = "tire_brands.txt"


def getDarknetCommand(image):
    config = os.path.join("cfg", "tire.cfg")
    weights = os.path.join("tire.weights")
    return "./darknet detect {} {} {}".format(config, weights, image)


def getRegionProposal(image):
    boxes = []
    regex = re.compile(r".*Left=(\d+), Top=(\d+), Right=(\d+), Bottom=(\d+)", re.I)
    command = getDarknetCommand(image)
    oldDir = os.getcwd()
    os.chdir(YOLO_FOLDER)
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
    os.chdir(oldDir)
    if process.returncode == 0:
        output = process.stdout.decode("utf-8").split("\n")
        for line in output:
            match = regex.search(line)
            if match:
                topLeft = (int(match.group(1)), int(match.group(2)))
                bottomRight = (int(match.group(3)), int(match.group(4)))
                boxes.append((topLeft, bottomRight))
        return boxes
    else:
        raise AssertionError("darknet failed to run.\nError: {}".format(process.stderr))


def findClosestMatch(text, brandNamesList):
    scores = {}
    for idx, name in enumerate(brandNamesList):
        matcher = SequenceMatcher(None, text, name)
        matcher.get_matching_blocks()
        score = round(matcher.ratio(), 2)
        scores[name] = score
    top = Counter(scores).most_common(1)[0]
    if top[1] > 0.6:
        return top[0], top[1]
    else:
        return None, None


def getTextFromImage(model, img):
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    converter = utils.strLabelConverter(alphabet)
    transformer = dataset.resizeNormalize((100, 32))

    img = transformer(img).cuda()
    img = img.view(1, *img.size())
    img = Variable(img)

    model.eval()
    preds = model(img)

    _, preds = preds.max(2)
    preds = preds.squeeze(1)
    preds = preds.transpose(0, 0).contiguous().view(-1)

    predictionSize = Variable(torch.IntTensor([preds.size(0)]))
    rawPrediction = converter.decode(preds.data, predictionSize.data, raw=True)
    decodedPrediction = converter.decode(preds.data, predictionSize.data, raw=False)
    return decodedPrediction


def _area(region):
    yield region
    for _ in range(3):
        x1, y1 = 0, 0
        x2, y2 = region.width, region.height
        newRegion = region.crop((x1 + x1 // 10, y1 + y1 // 10, x2 - x2 // 10, y2 - y2 // 10))
        yield newRegion
        region = newRegion


def _rotate(img, x1, y1, x2, y2):
    region = img.crop((x1, y1, x2, y2))
    for reg in _area(region):
        yield reg
    aspectRatio = region.height / region.width
    centerX = (x1 + x2) // 2
    if aspectRatio > 1:
        if centerX < img.width // 2:
            angle = -90
        else:
            angle = 90
    else:
        angle = 180
    rotRegion = region.rotate(angle, expand=True)
    for reg in _area(rotRegion):
        yield reg


def finder(model, img, x1, y1, x2, y2):
    topPred = None
    maxScore = None
    for region in _rotate(img, x1, y1, x2, y2):
        pred = getTextFromImage(model, region)
        text, score = findClosestMatch(pred, brandNamesList)
        if text:
            if maxScore is None:
                maxScore = score
                topPred = text
            else:
                if score > maxScore:
                    maxScore = score
                    topPred = text
    return topPred


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", help="Absolute path to location of tire image for text extraction(folder/file)", required=True)
    parser.add_argument("--saveFolder", help="Location where prediction should be stored",
                        required=False, default=None)
    args, _ = parser.parse_known_args()
    
    modelPath = os.path.join(CRNN_FOLDER, "crnn.pth")
    model = CRNN(imgH=32, nc=1, nclass=37, nh=256, ngpu=1).cuda()
    model.load_state_dict(torch.load(modelPath))
    imageList = []
    if os.path.isfile(args.images):
        image = str(Path(args.images).resolve())
        imageList = [image]
    elif os.path.isdir(args.images):
        imageList.extend(glob.glob(os.path.join(args.images, "*.jpg")))
    else:
        raise AssertionError("Value of --images must be a valid file or folder")
    if args.saveFolder:
        saveFolder = args.saveFolder
    else:
        saveFolder = os.path.join(os.getcwd(), "result")
    if not os.path.isdir(saveFolder):
        os.mkdir(saveFolder)

    brandNamesList = []
    with open(BRAND_FILE, "r") as fp:
        for line in fp:
            words = line.strip()
            brandNamesList.append(words.split(" ")[0].lower())

    font = ImageFont.truetype("LiberationSerif-Regular.ttf", 24, encoding="unic")
    for image in imageList:
        img = Image.open(image).convert('L')
        boxes = getRegionProposal(image)
        colorImg = Image.open(image)
        draw = ImageDraw.Draw(colorImg)
        for idx, box in enumerate(boxes):
            region = img.crop((box[0][0], box[0][1], box[1][0], box[1][1]))
            draw.rectangle(box, outline="#53f442", fill=None, width=3)
            text = finder(model, img, box[0][0], box[0][1], box[1][0], box[1][1])
            if text:
                draw.text((box[0][0], box[0][1] - 30), text, font=font)
        filename = os.path.basename(image)
        filename = filename.split(".")[0]
        colorImg.save(os.path.join(saveFolder, filename + ".jpg"), "JPEG")
