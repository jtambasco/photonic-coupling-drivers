import abc

class Logger(object, metaclass=abc.ABCMeta):
    def __init__(self, filename, stage):
        self.fs = open(filename, 'w')
        header = ('#input x + chip z [um],input y [um],input z [um],'
                  'output x + chip z [um],output y [um],output z [um]')
        self.fs.write(header+'\n')

    def __del__(self):
        self.fs.close()

    @abc.abstractmethod
    def log(self):
        pass

class LoggerStages3(Logger):
    def __init__(self, filename, stages):
        super().__init__(filename, stages)
        self.input = stages.input
        self.output = stages.output
        self.chip = stages.chip

    def log(self):
        x_in_nm = self.input.x._position_absolute
        y_in_nm = self.input.y._position_absolute
        z_in_nm = self.input.z._position_absolute
        xyz_in = [x_in_nm, y_in_nm, z_in_nm]

        x_out_nm = self.output.x._position_absolute
        y_out_nm = self.output.y._position_absolute
        z_out_nm = self.output.z._position_absolute
        xyz_out = [x_out_nm, y_out_nm, z_out_nm]

        z_chip_nm = self.chip.z._position_absolute
        xyz_in[0] += z_chip_nm
        xyz_out[0] += z_chip_nm

        # /1000.: nm -> um
        xyz_in_str = ','.join([str(v/1000.) for v in xyz_in])
        xyz_out_str = ','.join([str(v/1000.) for v in xyz_out])

        fs_str = '%s,%s\n' % (xyz_in_str, xyz_out_str)
        self.fs.write(fs_str)

        return fs_str

class LoggerStages2(Logger):
    def __init__(self, filename, stages):
        super().__init__(filename, stages)
        self.input = stages.input
        self.output = stages.output

    def log(self):
        x_in_nm = self.input.x._position_absolute
        y_in_nm = self.input.y._position_absolute
        z_in_nm = self.input.z._position_absolute
        xyz_in = [x_in_nm, y_in_nm, z_in_nm]

        x_out_nm = self.output.x._position_absolute
        y_out_nm = self.output.y._position_absolute
        z_out_nm = self.output.z._position_absolute
        xyz_out = [x_out_nm, y_out_nm, z_out_nm]

        # /1000.: nm -> um
        xyz_in_str = ','.join([str(v/1000.) for v in xyz_in])
        xyz_out_str = ','.join([str(v/1000.) for v in xyz_out])

        fs_str = '%s,%s\n' % (xyz_in_str, xyz_out_str)
        self.fs.write(fs_str)

        return fs_str

class LoggerStage(Logger):
    def __init__(self, filename, stage):
        super().__init__(filename, stage)
        self.stage = stage

    def log(self):
        x_st_nm = self.stage.x._position_absolute
        y_st_nm = self.stage.y._position_absolute
        z_st_nm = self.stage.z._position_absolute
        xyz_st = [x_st_nm, y_st_nm, z_st_nm]

        # /1000.: nm -> um
        xyz_st_str = ','.join([str(v/1000.) for v in xyz_st])

        fs_str = '%s\n' % xyz_st_str
        self.fs.write(fs_str)

        return fs_str

