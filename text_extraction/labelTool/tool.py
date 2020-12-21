from __future__ import division
from tkinter import *
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import glob

# colors for the bboxes
COLORS = ['red', 'blue', 'yellow', 'pink', 'cyan', 'green', 'black']


class TextPopupWindow(object):

    def __init__(self, master):
        self.popup = Toplevel(master)
        label = Label(self.popup, text="Enter Text:")
        label.pack()
        self.textBox = Entry(self.popup)
        self.textBox.pack()
        self.textBox.focus()
        self.button = Button(self.popup, text='Done', command=self.teardown)
        self.button.pack()
        self.value = None
        self.popup.bind("<Return>", self.teardownEvent)

    def teardown(self):
        self.value = self.textBox.get()
        self.popup.destroy()

    def teardownEvent(self, event):
        self.value = self.textBox.get()
        self.popup.destroy()


class LabelTool(object):

    def __init__(self, master):
        # set up the main frame
        self.parent = master
        self.parent.title("LabelTool")
        self.frame = Frame(self.parent)
        self.frame.pack(fill=BOTH, expand=1)
        self.parent.resizable(width=FALSE, height=FALSE)
        self.parent.focus()

        # initialize global state
        self.imageDir = ''
        self.imageList = []
        self.egDir = ''
        self.egList = []
        self.outDir = ''
        self.crnnDir = ''
        self.cur = 0
        self.total = 0
        self.category = 0
        self.imagename = ''
        self.labelfilename = ''
        self.textfilename = ''
        self.tkimg = None
        self.textPopup = None
        self.supportedImageExtension = ["*.jpg", "*.png", "*.JPEG"]

        # initialize mouse state
        self.STATE = {}
        self.STATE['click'] = 0
        self.STATE['x'], self.STATE['y'] = 0, 0

        # reference to bbox
        self.bboxIdList = []
        self.bboxId = None
        self.bboxList = []
        self.hl = None
        self.vl = None
        self.labelList = []

        # ----------------- GUI stuff ---------------------
        # dir entry & load
        self.label = Label(self.frame, text="Image Dir:")
        self.label.grid(row=0, column=0, sticky=E)
        self.loadDirText = Entry(self.frame)
        self.loadDirText.grid(row=0, column=1, sticky=W + E)
        self.loadDirText.focus()
        self.ldBtn = Button(self.frame, text="Load", command=self.loadDir)
        self.ldBtn.grid(row=0, column=2, sticky=W + E)

        # main panel for labeling
        self.mainPanel = Canvas(self.frame, cursor='tcross')
        self.mainPanel.bind("<Button-1>", self.mouseClick)
        self.mainPanel.bind("<Motion>", self.mouseMove)
        self.parent.bind("<Escape>", self.cancelBBox)  # press <Escape> to cancel current bbox
        # self.parent.bind("s", self.cancelBBox)
        # self.parent.bind("a", self.prevImage)  # press 'a' to go backforward
        # self.parent.bind("d", self.nextImage)  # press 'd' to go forward
        self.mainPanel.grid(row=1, column=1, rowspan=4, sticky=W + N)

        # showing bbox info & delete bbox
        self.lb1 = Label(self.frame, text='Bounding boxes:')
        self.lb1.grid(row=1, column=2, sticky=W + N)
        self.listbox = Listbox(self.frame, width=22, height=12)
        self.listbox.grid(row=2, column=2, sticky=N)
        self.btnDel = Button(self.frame, text='Delete', command=self.delBBox)
        self.btnDel.grid(row=3, column=2, sticky=W + E + N)
        self.btnClear = Button(self.frame, text='ClearAll', command=self.clearBBox)
        self.btnClear.grid(row=4, column=2, sticky=W + E + N)

        # control panel for image navigation
        self.ctrPanel = Frame(self.frame)
        self.ctrPanel.grid(row=5, column=1, columnspan=2, sticky=W + E)
        self.prevBtn = Button(self.ctrPanel, text='<< Prev', width=10, command=self.prevImage)
        self.prevBtn.pack(side=LEFT, padx=5, pady=3)
        self.nextBtn = Button(self.ctrPanel, text='Next >>', width=10, command=self.nextImage)
        self.nextBtn.pack(side=LEFT, padx=5, pady=3)
        self.progLabel = Label(self.ctrPanel, text="Progress:     /    ")
        self.progLabel.pack(side=LEFT, padx=5)
        self.tmpLabel = Label(self.ctrPanel, text="Go to Image No.")
        self.tmpLabel.pack(side=LEFT, padx=5)
        self.idxEntry = Entry(self.ctrPanel, width=5)
        self.idxEntry.pack(side=LEFT)
        self.goBtn = Button(self.ctrPanel, text='Go', command=self.gotoImage)
        self.goBtn.pack(side=LEFT)

        # example pannel for illustration
        self.egPanel = Frame(self.frame, border=10)
        self.egPanel.grid(row=1, column=0, rowspan=5, sticky=N)
        self.tmpLabel2 = Label(self.egPanel, text="Examples:")
        self.tmpLabel2.pack(side=TOP, pady=5)
        self.egLabels = []
        for i in range(3):
            self.egLabels.append(Label(self.egPanel))
            self.egLabels[-1].pack(side=TOP)

        # display mouse position
        self.disp = Label(self.ctrPanel, text='')
        self.disp.pack(side=RIGHT)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(4, weight=1)

    def loadDir(self):
        try:
            imageDir = self.loadDirText.get()
            if not os.path.isdir(imageDir):
                messagebox.showerror("Error", "Directory is invalid!")
                self.loadDirText.delete(0, END)
                return
            self.imageDir = imageDir
            for extension in self.supportedImageExtension:
                self.imageList.extend(glob.glob(os.path.join(self.imageDir, extension)))

            if len(self.imageList) == 0:
                messagebox.showwarning("Warning", "No supported images found in the specified dir!")
                self.loadDirText.delete(0, END)
                return

            # default to the 1st image in the collection
            self.cur = 1
            self.total = len(self.imageList)
            # set up output dir
            self.outDir = imageDir
            if not os.path.exists(self.outDir):
                os.mkdir(self.outDir)
            self.crnnDir = os.path.join(imageDir, "crnn")
            if not os.path.exists(self.crnnDir):
                os.mkdir(self.crnnDir)

            self.loadImage()
            messagebox.showinfo("Info", "{0} images loaded from {1}".format(self.total, self.imageDir))
        finally:
            self.parent.focus()
            self.loadDirText.focus()

    def loadImage(self):
        # load image
        imagepath = self.imageList[self.cur - 1]
        self.img = Image.open(imagepath)
        self.tkimg = ImageTk.PhotoImage(self.img)
        self.mainPanel.config(width=max(self.tkimg.width(), 400), height=max(self.tkimg.height(), 400))
        self.mainPanel.create_image(0, 0, image=self.tkimg, anchor=NW)
        self.progLabel.config(text="%04d/%04d" % (self.cur, self.total))

        # load labels
        self.clearBBox()
        self.imagename = os.path.split(imagepath)[-1].split('.')[0]
        labelname = self.imagename + '.txt'
        self.labelfilename = os.path.join(self.outDir, labelname)
        crnnImageList = glob.glob(os.path.join(self.crnnDir, "{}*.jpg".format(self.imagename)))
        self.labelList = [""] * len(crnnImageList)
        for imagePath in crnnImageList:
            image = os.path.split(imagePath)[-1].split('.')[0]
            match = re.search(r".*_([\w\d]+)_([\d]+)", image, re.I)
            if match:
                self.labelList[int(match.group(2))] = match.group(1)
        if os.path.exists(self.labelfilename):
            with open(self.labelfilename) as f:
                for idx, line in enumerate(f):
                    yolo = [float(t.strip()) for t in line.split()]
                    tmp = self.reverseYOLOFormat(yolo[1], yolo[2], yolo[3], yolo[4])
                    self.bboxList.append(yolo[1:])
                    tmpId = self.mainPanel.create_rectangle(
                        tmp[0], tmp[1], tmp[2], tmp[3],
                        width=2, outline=COLORS[(len(self.bboxList) - 1) % len(COLORS)])
                    self.bboxIdList.append(tmpId)
                    self.listbox.insert(END, '(%d, %d) -> (%d, %d)' % (tmp[0], tmp[1], tmp[2], tmp[3]))
                    self.listbox.itemconfig(len(self.bboxIdList) - 1,
                                            fg=COLORS[(len(self.bboxIdList) - 1) % len(COLORS)])

    def saveImage(self):
        filename = os.path.split(self.imageList[self.cur - 1])[-1].split('.')[0]
        self.labelfilename = os.path.join(self.outDir, filename + ".txt")
        if self.bboxList:
            with open(self.labelfilename, 'w') as f:
                for idx, bbox in enumerate(self.bboxList):
                    line = '0 ' + ' '.join(map(str, bbox)) + '\n'
                    yolo = [float(t.strip()) for t in line.split()]
                    tmp = self.reverseYOLOFormat(yolo[1], yolo[2], yolo[3], yolo[4])
                    path = os.path.join(self.crnnDir, "{}_{}_{}.jpg".format(filename,
                                                                            self.labelList[idx], idx))
                    self.img.crop((tmp[0], tmp[1], tmp[2], tmp[3])).save(path)
                    f.write(line)
            print('Image No. %d saved' % (self.cur))
        else:
            print('Image No. %d skipped!' % (self.cur))

    def openTextPopop(self):
        self.STATE['click'] = 1 - self.STATE['click']
        self.textPopup = TextPopupWindow(self.parent)
        self.parent.wait_window(self.textPopup.popup)

    def convertToYOLOFormat(self, x1, y1, x2, y2):
        """
        YOLO format:
        classId cx cy width height
        classId cx cy width height
        ...
        width = max(x1, x2) - min(x1, x2)
        height = max(y1, y2) - min(y1, y2)
        cx, cy = min(x1, x2) + width/2, min(y1, y2) + height/2

        NOTE: cx and cy are center of the box
        """
        imageWidth, imageHeight = self.img.size
        width = (max(x1, x2) - min(x1, x2)) / imageWidth
        height = (max(y1, y2) - min(y1, y2)) / imageHeight
        cx, cy = (min(x1, x2) / imageWidth) + width / 2, (min(y1, y2) / imageHeight) + height / 2
        return cx, cy, width, height

    def reverseYOLOFormat(self, cx, cy, width, height):
        """
        Convert yolo format of box to topLeft and bottomRight coordinates of box
        """
        imageWidth, imageHeight = self.img.size
        x1 = (cx - width / 2) * imageWidth
        x2 = (cx + width / 2) * imageWidth
        y1 = (cy - height / 2) * imageHeight
        y2 = (cy + height / 2) * imageHeight
        return x1, y1, x2, y2

    def mouseClick(self, event):
        popup = False
        if self.STATE['click'] == 0:
            self.STATE['x'], self.STATE['y'] = event.x, event.y
        else:
            x1, x2 = min(self.STATE['x'], event.x), max(self.STATE['x'], event.x)
            y1, y2 = min(self.STATE['y'], event.y), max(self.STATE['y'], event.y)
            bbox = self.convertToYOLOFormat(x1, y1, x2, y2)
            self.bboxList.append(bbox)
            self.bboxIdList.append(self.bboxId)
            self.bboxId = None
            self.listbox.insert(END, '(%d, %d) -> (%d, %d)' % (x1, y1, x2, y2))
            self.listbox.itemconfig(len(self.bboxIdList) - 1,
                                    fg=COLORS[(len(self.bboxIdList) - 1) % len(COLORS)])
            self.openTextPopop()
            self.labelList.append(self.textPopup.value)
            popup = True
        if not popup:
            self.STATE['click'] = 1 - self.STATE['click']
            popup = False

    def mouseMove(self, event):
        self.disp.config(text='x: %d, y: %d' % (event.x, event.y))
        if self.tkimg:
            if self.hl:
                self.mainPanel.delete(self.hl)
            self.hl = self.mainPanel.create_line(0, event.y, self.tkimg.width(), event.y, width=2)
            if self.vl:
                self.mainPanel.delete(self.vl)
            self.vl = self.mainPanel.create_line(event.x, 0, event.x, self.tkimg.height(), width=2)
        if 1 == self.STATE['click']:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
            self.bboxId = self.mainPanel.create_rectangle(self.STATE['x'], self.STATE['y'],
                                                          event.x, event.y,
                                                          width=2,
                                                          outline=COLORS[len(self.bboxList) % len(COLORS)])

    def cancelBBox(self, event):
        if 1 == self.STATE['click']:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
                self.bboxId = None
                self.STATE['click'] = 0

    def delBBox(self):
        sel = self.listbox.curselection()
        if len(sel) != 1:
            return
        idx = int(sel[0])
        self.mainPanel.delete(self.bboxIdList[idx])
        self.bboxIdList.pop(idx)
        self.bboxList.pop(idx)
        self.labelList.pop(idx)
        self.listbox.delete(idx)

    def clearBBox(self):
        for idx in range(len(self.bboxIdList)):
            self.mainPanel.delete(self.bboxIdList[idx])
        self.listbox.delete(0, len(self.bboxList))
        self.bboxIdList = []
        self.bboxList = []
        self.labelList = []

    def prevImage(self, event=None):
        self.saveImage()
        if self.cur > 1:
            self.cur -= 1
            self.loadImage()

    def nextImage(self, event=None):
        self.saveImage()
        if self.cur < self.total:
            self.cur += 1
            self.loadImage()

    def gotoImage(self):
        idx = int(self.idxEntry.get())
        if 1 <= idx and idx <= self.total:
            self.saveImage()
            self.cur = idx
            self.loadImage()


if __name__ == '__main__':
    root = Tk()
    tool = LabelTool(root)
    root.resizable(width=True, height=True)
    root.wm_iconbitmap('acv.ico')
    root.mainloop()
