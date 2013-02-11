"""
Exports the slicedFile to a file.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from datetime import timedelta
from fabmetheus_utilities import archive, euclidean
from utilities import memory_tracker
from writers.gcode_writer import GcodeWriter
from StringIO import StringIO
import datetime
import logging
import os
import string
import time
import sys
try:
    import cPickle as pickle
except:
    import pickle

name = 'export'
logger = logging.getLogger(name)


def performAction(slicedFile):
    'Export a slicedFile linear move text.'
    e = ExportSkein(slicedFile)
    if slicedFile.runtimeParameters.profileMemory:
        memory_tracker.track_object(e)
    e.export()
    if slicedFile.runtimeParameters.profileMemory:
        memory_tracker.create_snapshot("After export")


class ExportSkein:
    'A class to export a skein of extrusions.'

    def __init__(self, slicedFile):
        self.slicedFile = slicedFile
        self.debug = config.getboolean(name, 'debug')
        self.deleteComments = config.getboolean(name, 'delete.comments')
        self.fileExtension = config.get(name, 'file.extension')
        self.nameOfReplaceFile = config.get(name, 'replace.filename')
        self.exportSlicedFile = config.getboolean(name, 'export.slicedfile')
        self.exportSlicedFileExtension = config.get(name, 'export.slicedfile.extension')
        self.addProfileExtension = config.getboolean(name, 'file.extension.profile')
        self.overwriteExportedSlicedFile = config.getboolean(name, 'overwrite.exported.slicedfile')

    def getReplaceableExportGcode(self, nameOfReplaceFile, replaceableExportGcode):
        'Get text with strings replaced according to replace.csv file.'

        fullReplaceFilePath = os.path.join('alterations', nameOfReplaceFile)

        if self.nameOfReplaceFile == '' or not os.path.exists(fullReplaceFilePath):
            return replaceableExportGcode

        fullReplaceText = archive.getFileText(fullReplaceFilePath)
        replaceLines = archive.getTextLines(fullReplaceText)
        if len(replaceLines) < 1:
            return replaceableExportGcode
        for replaceLine in replaceLines:
            splitLine = replaceLine.replace('\\n', '\t').split('\t')
            if len(splitLine) > 0:
                replaceableExportGcode = replaceableExportGcode.replace(splitLine[0], '\n'.join(splitLine[1:]))
        output = StringIO()

        for line in archive.getTextLines(replaceableExportGcode):
            if line != '':
                output.write(line + '\n')

        return output.getvalue()

    def export(self):
        'Perform final modifications to slicedFile and performs export.'

        filename = self.slicedFile.fileName
        filenamePrefix = os.path.splitext(filename)[0]
        profileName = self.slicedFile.runtimeParameters.profileName

        if self.slicedFile.runtimeParameters.outputFilename is not None:
            exportFileName = self.slicedFile.runtimeParameters.outputFilename
        else:
            exportFileName = filenamePrefix
            if self.addProfileExtension and profileName:
                exportFileName += '.' + string.replace(profileName, ' ', '_')
            exportFileName += '.' + self.fileExtension
            self.slicedFile.runtimeParameters.outputFilename = exportFileName

        replaceableExportGcode = self.getReplaceableExportGcode(self.nameOfReplaceFile, GcodeWriter(self.slicedFile).getSlicedFile())
        archive.writeFileText(exportFileName, replaceableExportGcode)
        logger.info('Gcode exported to: %s', os.path.basename(exportFileName))

        if self.debug:
            slicedFileTextFilename = filenamePrefix
            if self.addProfileExtension and profileName:
                slicedFileTextFilename += '.' + string.replace(profileName, ' ', '_')
            slicedFileTextFilename += '.slicedfile.txt'
            archive.writeFileText(slicedFileTextFilename, str(self.slicedFile))
            logger.info('Sliced File Text exported to: %s', slicedFileTextFilename)

        if self.exportSlicedFile:
            slicedFileExportFilename = filenamePrefix
            if self.addProfileExtension and profileName:
                slicedFileExportFilename += '.' + string.replace(profileName, ' ', '_')
            slicedFileExportFilename += '.' + self.exportSlicedFileExtension
            if os.path.exists(slicedFileExportFilename) and not self.overwriteExportedSlicedFile:
                backupFilename = '%s.%s.bak' % (slicedFileExportFilename, datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
                os.rename(slicedFileExportFilename, backupFilename)
                logger.info('Existing slicedfile file backed up to: %s', backupFilename)
            logger.info('Sliced File exported to: %s', slicedFileExportFilename)
            archive.writeFileText(slicedFileExportFilename, pickle.dumps(self.slicedFile))
