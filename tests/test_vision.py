import unittest
import numpy as np
import vision

class TestVision(unittest.TestCase):
    def test_background_ignored(self):
        a = np.zeros((10,10,3), dtype=np.uint8)
        b = np.full((10,10,3), 255, dtype=np.uint8)
        mask = np.zeros((10,10), dtype=np.uint8)
        mask[2:8,2:8] = 255
        b[mask>0] = a[mask>0]
        similarity, brightness = vision.score(a,b,mask)
        self.assertEqual(similarity, 1.0)
        self.assertEqual(brightness, 0.0)
    def test_different_selected_pixels(self):
        a = np.zeros((4,4,3), dtype=np.uint8)
        b = np.full((4,4,3), 255, dtype=np.uint8)
        mask = np.full((4,4), 255, dtype=np.uint8)
        similarity, brightness = vision.score(a,b,mask)
        self.assertEqual(similarity, 0.0)
        self.assertAlmostEqual(brightness, 1.0)
    def test_empty_mask_fails(self):
        a = np.zeros((4,4,3), dtype=np.uint8)
        with self.assertRaises(ValueError): vision.score(a,a,np.zeros((4,4), dtype=np.uint8))

if __name__ == '__main__': unittest.main()
