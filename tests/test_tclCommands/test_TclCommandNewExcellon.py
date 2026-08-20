from FlatCAMObj import FlatCAMExcellon


def test_new_excellon(self):
    name = "blank_exc"
    self.fc.exec_command_test('new_excellon "%s"' % name)
    obj = self.fc.collection.get_by_name(name)
    self.assertIsInstance(obj, FlatCAMExcellon)
    self.assertEqual(obj.drills, [])
    self.assertEqual(obj.tools, {})
