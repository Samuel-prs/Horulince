import unittest
from unittest.mock import patch

import cv2
import numpy as np

from horulince.vision import PlateRegion, locate_plate_regions, read_plate


def ocr_data(words, confidence=85, tops=None):
    return {"text":words,"conf":[confidence]*len(words),"top":tops or [20]*len(words),
            "height":[25]*len(words),"left":[10+80*i for i in range(len(words))],
            "block_num":[1]*len(words),"par_num":[1]*len(words),"line_num":[1]*len(words)}


class OCRTests(unittest.TestCase):
    def setUp(self):
        self.vehicle = np.full((180,300,3),180,dtype=np.uint8)
        self.regions = [PlateRegion(np.full((24,120,3),220,dtype=np.uint8),(10,80,130,104),"teste",1)]

    def test_two_variants_remain_one_read_not_a_temporal_consensus(self):
        with patch("horulince.vision.locate_plate_regions",return_value=self.regions), patch(
                "horulince.vision.pytesseract.image_to_data",return_value=ocr_data(["ABC1D23"])) as ocr:
            diagnostics = {}
            self.assertEqual(read_plate(self.vehicle,diagnostics=diagnostics),("ABC1D23",85))
            self.assertEqual(ocr.call_count,2)
            self.assertEqual(diagnostics["status"],"leitura_valida")
            self.assertNotIn("leituras",diagnostics)

    def test_fragments_are_joined_only_within_the_same_region(self):
        with patch("horulince.vision.locate_plate_regions",return_value=self.regions), patch(
                "horulince.vision.pytesseract.image_to_data",return_value=ocr_data(["ABC","1D23"])):
            self.assertEqual(read_plate(self.vehicle)[0],"ABC1D23")
        with patch("horulince.vision.locate_plate_regions",return_value=self.regions*2), patch(
                "horulince.vision.pytesseract.image_to_data",side_effect=[
                    ocr_data(["ABC","1D23"],tops=[20,116]),ocr_data(["ABC","1D23"],tops=[20,116]),
                    ocr_data([]),ocr_data([])]):
            self.assertIsNone(read_plate(self.vehicle)[0])

    def test_low_confidence_and_conflicts_never_become_accepted_reads(self):
        for data,status in [(ocr_data(["ABC1D23"],20),"baixa_confianca"),
                            (ocr_data(["ABC1D23","XYZ9876"]),"conflito")]:
            with self.subTest(status=status),patch("horulince.vision.locate_plate_regions",return_value=self.regions),patch(
                    "horulince.vision.pytesseract.image_to_data",return_value=data):
                diagnostics={}
                self.assertEqual(read_plate(self.vehicle,diagnostics=diagnostics),(None,0))
                self.assertEqual(diagnostics["status"],status)

    def test_timeout_is_visible_without_aborting_the_video(self):
        with patch("horulince.vision.locate_plate_regions",return_value=self.regions),patch(
                "horulince.vision.pytesseract.image_to_data",side_effect=RuntimeError("Tesseract process timeout")) as ocr:
            diagnostics={}
            self.assertIsNone(read_plate(self.vehicle,diagnostics=diagnostics)[0])
            self.assertEqual(diagnostics["status"],"timeout")
            self.assertEqual(ocr.call_count,1)

    def test_missing_region_does_not_launch_tesseract(self):
        with patch("horulince.vision.locate_plate_regions",return_value=[]),patch(
                "horulince.vision.pytesseract.image_to_data") as ocr:
            diagnostics={}
            self.assertIsNone(read_plate(self.vehicle,diagnostics=diagnostics)[0])
            self.assertEqual(diagnostics["status"],"sem_regiao")
            ocr.assert_not_called()

    def test_locator_finds_text_on_a_white_vehicle(self):
        image=np.full((260,420,3),225,dtype=np.uint8)
        cv2.rectangle(image,(115,165),(305,214),(200,200,200),-1)
        cv2.putText(image,"ABC1D23",(120,200),cv2.FONT_HERSHEY_SIMPLEX,.85,(20,20,20),2)
        regions=locate_plate_regions(image)
        self.assertTrue(regions)
        self.assertTrue(any(r.box[0] <= 125 and r.box[2] >= 235 and r.box[1] <= 190 and r.box[3] >= 200 for r in regions))


if __name__ == "__main__":
    unittest.main()
