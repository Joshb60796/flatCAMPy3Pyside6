from FlatCAMObj import FlatCAMExcellon, FlatCAMCNCjob


def test_new_excellon_add_drill_and_cnc(self):
    name = "holes"
    self.fc.exec_command_test('new_excellon "%s"' % name)
    obj = self.fc.collection.get_by_name(name)
    self.assertIsInstance(obj, FlatCAMExcellon)

    self.fc.exec_command_test('add_drill "%s" 1.0 2.0 -dia 0.8' % name)
    self.fc.exec_command_test('add_drill "%s" 3.0 4.0 -dia 0.8' % name)
    obj = self.fc.collection.get_by_name(name)
    self.assertEqual(len(obj.drills), 2)

    self.fc.exec_command_test(
        'drillcncjob "%s" -tools all -drillz -1.6 -travelz 5 -feedrate 80 '
        "-multidepth 1 -depthperpass 0.4 -outname holes_cnc" % name
    )
    job = self.fc.collection.get_by_name("holes_cnc")
    self.assertIsInstance(job, FlatCAMCNCjob)
    self.assertIn("G01", job.gcode)
    self.assertIn("Z-1.6000", job.gcode)
