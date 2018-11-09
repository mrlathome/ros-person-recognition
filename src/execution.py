"""
Creates the necessary objects and executes functions of the system.
"""

import os
from copy import deepcopy

import cv2

from data_acquisition import CamStreamer
from data_acquisition import DataAcquisition
from data_acquisition import Face
from data_acquisition import Warehouse
from data_processing import DataProcessing
from model_engineering import ModelEngineering


class Execution:
    def __init__(self, pkg_dir):
        self.pkg_dir = pkg_dir
        self.data_acquisition = DataAcquisition()
        self.data_processing = DataProcessing()
        self.model_engineering = ModelEngineering(self.pkg_dir)
        self.cam_streamer = CamStreamer()
        self.acquire_data()
        self.model_engineering.knn_fit(self.data_acquisition.trn_wh)

    def acquire_data(self):
        """
        Read data sets, process them, and create warehouses for storing them
        :return: None
        """
        trn_dir = os.path.join(self.pkg_dir, 'dataset', 'train')
        tst_dir = os.path.join(self.pkg_dir, 'dataset', 'test')
        self.data_acquisition.trn_wh = self.create_wh(trn_dir)
        self.data_acquisition.tst_wh = self.create_wh(tst_dir)
        for face in self.data_acquisition.trn_wh.get_faces():
            face.embedding = self.model_engineering.encode([face.image])
        for face in self.data_acquisition.tst_wh.get_faces():
            face.embedding = self.model_engineering.encode([face.image])

    def visualize(self, image, bbox, uid):
        """
        Visualize a bounding box in an image
        :param sample: an image
        :return: the image overlaid with the bounding box
        """
        if bbox is None:
            return image
        _image = deepcopy(image)
        xmin, ymin, xmax, ymax = bbox
        start_pt = (xmin, ymin)
        end_pt = (xmax, ymax)
        color = (255, 0, 0)
        thickness = 1
        cv2.rectangle(_image, start_pt, end_pt, color, thickness)
        thickness = 1
        color = (255, 255, 255)
        origin = start_pt
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        cv2.putText(_image, str(uid), origin, font, font_scale, color, thickness, cv2.LINE_AA)
        return _image

    def id(self, image):
        """
        Identifies the person present in the image
        :param image: The input image
        :return: The UID of the person
        """
        # bbox = self.data_processing.detect_faces(image)
        # face_image = self.data_processing.crop(image, bbox)
        face_image = self.data_processing.process(image)
        embedding = self.model_engineering.encode([face_image])[0]
        uid = self.model_engineering.knn_classify(embedding)
        return uid

    def evaluate(self):
        """
        Evaluates the accuracy of the model on the test set
        :return: the true positive rate
        """
        accuracy = self.model_engineering.knn_eval(self.data_acquisition.tst_wh)
        return accuracy

    def test(self):
        """
        Performing different tests
        :return: None
        """
        stop = False
        while not stop:
            image = self.cam_streamer.get_frame()
            if image is None or not image.shape[0] > 0 or not image.shape[1] > 0:
                continue
            # print('image.shape', image.shape)

            bboxes = self.data_processing.detect_faces(image)
            selected_face = None
            selected_uid = -1
            for bbox in bboxes:
                cropped_face = self.data_processing.crop(image, bbox)
                face = self.data_processing.process(cropped_face)
                embedding = self.model_engineering.encode([face])
                uid = self.model_engineering.knn_classify(embedding[0])
                image = self.visualize(image, bbox, uid)
                selected_face = cropped_face
                selected_uid = uid

            cv2.imshow('image', image)
            k = cv2.waitKey(30)
            if k == 27:  # wait for ESC key to exit
                self.cam_streamer.release()
                cv2.destroyAllWindows()
                stop = True
            elif k == ord('s'):  # wait for 's' key to save and exit
                cv2.imwrite('face.jpg', image)
            elif k == ord('a'):  # wait for 'a' key
                if selected_face is not None:
                    image_path = self.find_path(selected_uid)
                    cv2.imwrite(image_path, selected_face)
                    self.acquire_data()
                    self.model_engineering.knn_fit(self.data_acquisition.trn_wh)
            elif k == ord('d'):  # wait for 'd' key
                if selected_uid != -1:
                    images_paths = self.find_all_files(selected_uid)
                    for path in images_paths:
                        os.remove(path)
                    self.acquire_data()
                    self.model_engineering.knn_fit(self.data_acquisition.trn_wh)

    def find_all_files(self, uid):
        """
        Find all of the files paths related to the query UID
        :param uid: the query UID
        :return: a list of paths
        """
        dataset_dir = os.path.join(self.pkg_dir, 'dataset', 'train')
        samples_num = 0
        for file in os.listdir(dataset_dir):
            name_parts = file.split('.')
            if name_parts[-1] == 'jpg':
                image_uid = name_parts[0]
                if int(image_uid) == uid:
                    samples_num += 1
        paths = []
        for sample in range(samples_num):
            del_face_uid = str(uid).zfill(4)
            del_face_number = str(sample).zfill(4)
            file_name = '{}.{}.jpg'.format(del_face_uid, del_face_number)
            image_path = os.path.join(dataset_dir, file_name)
            paths.append(image_path)
        return paths

    def find_path(self, uid):
        """
        Find an image path to save
        :param uid: the selected UID for the image
        :return: the image path
        """
        dataset_dir = os.path.join(self.pkg_dir, 'dataset', 'train')
        if uid == -1:
            persons = self.data_acquisition.trn_wh.get_persons()
            existing_uids = []
            for person in persons:
                existing_uids.append(person.uid)
            new_uid = 0
            while new_uid in existing_uids:
                new_uid += 1
            new_face_uid = str(new_uid).zfill(4)
            new_face_number = str(0).zfill(4)
            print('UID: -1', 'new_face_uid', new_face_uid)
            print('UID: -1', 'new_face_number', new_face_number)
        else:
            samples_num = 0
            for file in os.listdir(dataset_dir):
                name_parts = file.split('.')
                if name_parts[-1] == 'jpg':
                    image_uid = name_parts[0]
                    if int(image_uid) == uid:
                        samples_num += 1
            new_face_uid = str(uid).zfill(4)
            new_face_number = str(samples_num).zfill(4)
            print('UID: not -1', 'new_face_uid', new_face_uid)
            print('UID: not -1', 'new_face_number', new_face_number)
        file_name = '{}.{}.jpg'.format(new_face_uid, new_face_number)
        image_path = os.path.join(dataset_dir, file_name)
        return image_path

    def create_wh(self, directory):
        """
        Read a data set and create a new warehouse
        :param directory: the directory of the data set
        :return: the warehouse containing the data set
        """
        warehouse = Warehouse()
        for file in os.listdir(directory):
            name_parts = file.split('.')
            if name_parts[-1] == 'jpg':
                image_path = os.path.join(directory, file)
                image = cv2.imread(image_path)
                bboxes = self.data_processing.detect_faces(image)
                for bbox in bboxes:
                    face = Face()
                    face_img = self.data_processing.crop(image, bbox)
                    face_img = self.data_processing.process(face_img)
                    label = int(name_parts[0])
                    face.image = face_img
                    face.uid = label
                    warehouse.add(face)
        return warehouse
