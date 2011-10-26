"""
Inset will inset the outside outlines by half the perimeter width, and outset the inside outlines by the same amount.
"""

from config import config
from fabmetheus_utilities import archive, euclidean, gcodec, intercircle
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
import math
import os
import sys
import logging

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text, gcode):
	"Inset the preface file or text."
	if config.getboolean(name, 'debug'):
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.pre.inset', text)
	gcodeText = InsetSkein(gcode).getCraftedGcode(text)
	if config.getboolean(name, 'debug'):
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.post.inset', gcodeText)
	return gcodeText

def addAlreadyFilledArounds(alreadyFilledArounds, loop, radius):
	"Add already filled loops around loop to alreadyFilledArounds."
	radius = abs(radius)
	alreadyFilledLoop = []
	slightlyGreaterThanRadius = 1.01 * radius
	muchGreaterThanRadius = 2.5 * radius
	centers = intercircle.getCentersFromLoop(loop, slightlyGreaterThanRadius)
	for center in centers:
		alreadyFilledInset = intercircle.getSimplifiedInsetFromClockwiseLoop(center, radius)
		if intercircle.isLargeSameDirection(alreadyFilledInset, center, radius):
			alreadyFilledLoop.append(alreadyFilledInset)
	if len(alreadyFilledLoop) > 0:
		alreadyFilledArounds.append(alreadyFilledLoop)

def addSegmentOutline(isThick, outlines, pointBegin, pointEnd, width):
	"Add a diamond or hexagonal outline for a line segment."
	width = abs(width)
	exclusionWidth = 0.6 * width
	slope = 0.2
	if isThick:
		slope = 3.0
		exclusionWidth = 0.8 * width
	segment = pointEnd - pointBegin
	segmentLength = abs(segment)
	if segmentLength == 0.0:
		return
	normalizedSegment = segment / segmentLength
	outline = []
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointBeginRotated = segmentYMirror * pointBegin
	pointEndRotated = segmentYMirror * pointEnd
	along = 0.05
	alongLength = along * segmentLength
	if alongLength > 0.1 * exclusionWidth:
		along *= 0.1 * exclusionWidth / alongLength
	alongEnd = 1.0 - along
	remainingToHalf = 0.5 - along
	alongToWidth = exclusionWidth / slope / segmentLength
	pointBeginIntermediate = euclidean.getIntermediateLocation(along, pointBeginRotated, pointEndRotated)
	pointEndIntermediate = euclidean.getIntermediateLocation(alongEnd, pointBeginRotated, pointEndRotated)
	outline.append(pointBeginIntermediate)
	verticalWidth = complex(0.0, exclusionWidth)
	if alongToWidth > 0.9 * remainingToHalf:
		verticalWidth = complex(0.0, slope * remainingToHalf * segmentLength)
		middle = (pointBeginIntermediate + pointEndIntermediate) * 0.5
		middleDown = middle - verticalWidth
		middleUp = middle + verticalWidth
		outline.append(middleUp)
		outline.append(pointEndIntermediate)
		outline.append(middleDown)
	else:
		alongOutsideBegin = along + alongToWidth
		alongOutsideEnd = alongEnd - alongToWidth
		outsideBeginCenter = euclidean.getIntermediateLocation(alongOutsideBegin, pointBeginRotated, pointEndRotated)
		outsideBeginCenterDown = outsideBeginCenter - verticalWidth
		outsideBeginCenterUp = outsideBeginCenter + verticalWidth
		outsideEndCenter = euclidean.getIntermediateLocation(alongOutsideEnd, pointBeginRotated, pointEndRotated)
		outsideEndCenterDown = outsideEndCenter - verticalWidth
		outsideEndCenterUp = outsideEndCenter + verticalWidth
		outline.append(outsideBeginCenterUp)
		outline.append(outsideEndCenterUp)
		outline.append(pointEndIntermediate)
		outline.append(outsideEndCenterDown)
		outline.append(outsideBeginCenterDown)
	outlines.append(euclidean.getPointsRoundZAxis(normalizedSegment, outline))

def getInteriorSegments(loops, segments):
	'Get segments inside the loops.'
	interiorSegments = []
	for segment in segments:
		center = 0.5 * (segment[0].point + segment[1].point)
		if euclidean.getIsInFilledRegion(loops, center):
			interiorSegments.append(segment)
	return interiorSegments

def getIsIntersectingWithinList(loop, loopList):
	"Determine if the loop is intersecting or is within the loop list."
	leftPoint = euclidean.getLeftPoint(loop)
	for otherLoop in loopList:
		if euclidean.getNumberOfIntersectionsToLeft(otherLoop, leftPoint) % 2 == 1:
			return True
	return euclidean.isLoopIntersectingLoops(loop, loopList)


def getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd):
	"Get endpoint segments from the beginning and end of a line segment."
	normalizedSegment = pointEnd - pointBegin
	normalizedSegmentLength = abs(normalizedSegment)
	if normalizedSegmentLength == 0.0:
		return []
	normalizedSegment /= normalizedSegmentLength
	segmentYMirror = complex(normalizedSegment.real, -normalizedSegment.imag)
	pointBeginRotated = segmentYMirror * pointBegin
	pointEndRotated = segmentYMirror * pointEnd
	rotatedLoopLists = []
	for loopList in loopLists:
		rotatedLoopList = []
		rotatedLoopLists.append(rotatedLoopList)
		for loop in loopList:
			rotatedLoop = euclidean.getPointsRoundZAxis(segmentYMirror, loop)
			rotatedLoopList.append(rotatedLoop)
	xIntersectionIndexList = []
	xIntersectionIndexList.append(euclidean.XIntersectionIndex(-1, pointBeginRotated.real))
	xIntersectionIndexList.append(euclidean.XIntersectionIndex(-1, pointEndRotated.real))
	euclidean.addXIntersectionIndexesFromLoopListsY(rotatedLoopLists, xIntersectionIndexList, pointBeginRotated.imag)
	segments = euclidean.getSegmentsFromXIntersectionIndexes(xIntersectionIndexList, pointBeginRotated.imag)
	for segment in segments:
		for endpoint in segment:
			endpoint.point *= normalizedSegment
	return segments

def isCloseToLast(paths, point, radius):
	"Determine if the point is close to the last point of the last path."
	if len(paths) < 1:
		return False
	lastPath = paths[-1]
	return abs(lastPath[-1] - point) < radius

def isIntersectingItself(loop, width):
	"Determine if the loop is intersecting itself."
	outlines = []
	for pointIndex in xrange(len(loop)):
		pointBegin = loop[pointIndex]
		pointEnd = loop[(pointIndex + 1) % len(loop)]
		if euclidean.isLineIntersectingLoops(outlines, pointBegin, pointEnd):
			return True
		addSegmentOutline(False, outlines, pointBegin, pointEnd, width)
	return False

def isIntersectingWithinLists(loop, loopLists):
	"Determine if the loop is intersecting or is within the loop lists."
	for loopList in loopLists:
		if getIsIntersectingWithinList(loop, loopList):
			return True
	return False

class InsetSkein:
	"A class to inset a skein of extrusions."
	def __init__(self, gcode):
		self.boundary = None
		self.gcodeCodec = gcodec.Gcode()
		self.lineIndex = 0
		self.rotatedLoopLayer = None
		self.overlapRemovalWidthOverPerimeterWidth = config.getfloat(name, 'overlap.removal.scaler')
		self.nozzleDiameter = config.getfloat(name, 'nozzle.diameter')
		self.bridgeWidthMultiplier = config.getfloat(name, 'bridge.width.multiplier.ratio')
		self.loopOrderAscendingArea = config.getboolean(name, 'loop.order.preferloops')
		
		self.gcode = gcode
		self.layerThickness = self.gcode.runtimeParameters.layerThickness
		self.perimeterWidth = self.gcode.runtimeParameters.perimeterWidth
		self.halfPerimeterWidth = 0.5 * self.perimeterWidth
		self.overlapRemovalWidth = self.perimeterWidth * (0.7853) * self.overlapRemovalWidthOverPerimeterWidth
		
		self.gcode.runtimeParameters.bridgeWidthMultiplier = self.bridgeWidthMultiplier
		self.gcode.runtimeParameters.nozzleDiameter = self.nozzleDiameter
		
	def addGcodeFromPerimeterPaths(self, isIntersectingSelf, loop, loopLists, radius, rotatedLoopLayer):
		"Add the perimeter paths to the output."
		segments = []
		outlines = []
		thickOutlines = []
		allLoopLists = loopLists[:] + [thickOutlines]
		aroundLists = loopLists
		for pointIndex in xrange(len(loop)):
			pointBegin = loop[pointIndex]
			pointEnd = loop[(pointIndex + 1) % len(loop)]
			if isIntersectingSelf:
				if euclidean.isLineIntersectingLoops(outlines, pointBegin, pointEnd):
					segments += getSegmentsFromLoopListsPoints(allLoopLists, pointBegin, pointEnd)
				else:
					segments += getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd)
				addSegmentOutline(False, outlines, pointBegin, pointEnd, self.overlapRemovalWidth)
				addSegmentOutline(True, thickOutlines, pointBegin, pointEnd, self.overlapRemovalWidth)
			else:
				segments += getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd)
		perimeterPaths = []
		path = []
		muchSmallerThanRadius = 0.1 * radius
		segments = getInteriorSegments(rotatedLoopLayer.loops, segments)
		for segment in segments:
			pointBegin = segment[0].point
			if not isCloseToLast(perimeterPaths, pointBegin, muchSmallerThanRadius):
				path = [pointBegin]
				perimeterPaths.append(path)
			path.append(segment[1].point)
		if len(perimeterPaths) > 1:
			firstPath = perimeterPaths[0]
			lastPath = perimeterPaths[-1]
			if abs(lastPath[-1] - firstPath[0]) < 0.1 * muchSmallerThanRadius:
				connectedBeginning = lastPath[:-1] + firstPath
				perimeterPaths[0] = connectedBeginning
				perimeterPaths.remove(lastPath)
		muchGreaterThanRadius = 6.0 * radius
		for perimeterPath in perimeterPaths:
			if euclidean.getPathLength(perimeterPath) > muchGreaterThanRadius:
				self.gcodeCodec.addGcodeFromThreadZ(perimeterPath, rotatedLoopLayer.z)

	def addGcodeFromRemainingLoop(self, loop, loopLists, radius, rotatedLoopLayer):
		"Add the remainder of the loop which does not overlap the alreadyFilledArounds loops."
		centerOutset = intercircle.getLargestCenterOutsetLoopFromLoopRegardless(loop, radius)
		euclidean.addSurroundingLoopBeginning(self.gcodeCodec, centerOutset.outset, rotatedLoopLayer.z)
		self.addGcodePerimeterBlockFromRemainingLoop(centerOutset.center, loopLists, radius, rotatedLoopLayer)
		self.gcodeCodec.addLine('(</boundaryPerimeter>)')
		self.gcodeCodec.addLine('(</nestedRing>)')

	def addGcodePerimeterBlockFromRemainingLoop(self, loop, loopLists, radius, rotatedLoopLayer):
		"Add the perimeter block remainder of the loop which does not overlap the alreadyFilledArounds loops."
		
		if self.overlapRemovalWidthOverPerimeterWidth < 0.1:
			self.gcodeCodec.addPerimeterBlock(loop, rotatedLoopLayer.z)
			return
		isIntersectingSelf = isIntersectingItself(loop, self.overlapRemovalWidth)
		if isIntersectingWithinLists(loop, loopLists) or isIntersectingSelf:
			self.addGcodeFromPerimeterPaths(isIntersectingSelf, loop, loopLists, radius, rotatedLoopLayer)
		else:
			self.gcodeCodec.addPerimeterBlock(loop, rotatedLoopLayer.z)
		addAlreadyFilledArounds(loopLists, loop, self.overlapRemovalWidth)

	def addInset(self, rotatedLoopLayer):
		"Add inset to the layer."
		alreadyFilledArounds = []
		halfWidth = self.halfPerimeterWidth * 0.7853 #todo was without 0,7853
		if rotatedLoopLayer.rotation != None:
			halfWidth = self.bridgeWidthMultiplier * ((2 * self.nozzleDiameter - self.layerThickness) / 2) * 0.7853
			self.gcodeCodec.addTagBracketedLine('bridgeRotation', rotatedLoopLayer.rotation)
		extrudateLoops = intercircle.getInsetLoopsFromLoops(halfWidth, rotatedLoopLayer.loops)
		triangle_mesh.sortLoopsInOrderOfArea(not self.loopOrderAscendingArea, extrudateLoops)
		for extrudateLoop in extrudateLoops:
			self.addGcodeFromRemainingLoop(extrudateLoop, alreadyFilledArounds, halfWidth, rotatedLoopLayer)

	def addInsetToGcode(self, rotatedLoopLayer):
		"Add inset to the layer."
		alreadyFilledArounds = []
		halfWidth = self.halfPerimeterWidth * 0.7853
		if rotatedLoopLayer.rotation != None:
			halfWidth = self.bridgeWidthMultiplier * ((2 * self.nozzleDiameter - self.layerThickness) / 2) * 0.7853
		extrudateLoops = intercircle.getInsetLoopsFromLoops(halfWidth, rotatedLoopLayer.loops)
		triangle_mesh.sortLoopsInOrderOfArea(not self.loopOrderAscendingArea, extrudateLoops)
		z = rotatedLoopLayer.z
		layer = self.gcode.layers[z]
		layer.boundaryPerimeters = []
		#print "z",z
		for loop in extrudateLoops:
			#self.addGcodeFromRemainingLoop(extrudateLoop, alreadyFilledArounds, halfWidth, rotatedLoopLayer)
			#"Add the remainder of the loop which does not overlap the alreadyFilledArounds loops."
			centerOutset = intercircle.getLargestCenterOutsetLoopFromLoopRegardless(loop, halfWidth)
			
			#euclidean.addSurroundingLoopBeginning(self.gcodeCodec, centerOutset.outset, rotatedLoopLayer.z)
				#distanceFeedRate.addLine(distanceFeedRate.getBoundaryLine(pointVector3))
			#self.addGcodePerimeterBlockFromRemainingLoop(centerOutset.center, alreadyFilledArounds, halfWidth, rotatedLoopLayer)
			#def addGcodePerimeterBlockFromRemainingLoop(self, loop, loopLists, radius, rotatedLoopLayer):
			"Add the perimeter block remainder of the loop which does not overlap the alreadyFilledArounds loops."
			if self.overlapRemovalWidthOverPerimeterWidth < 0.1:
				#self.gcodeCodec.addPerimeterBlock(centerOutset.center, rotatedLoopLayer.z)
				layer.addBoundaryPerimeter(centerOutset.center)
				break
			isIntersectingSelf = isIntersectingItself(centerOutset.center, self.overlapRemovalWidth)
			if isIntersectingWithinLists(centerOutset.center, alreadyFilledArounds) or isIntersectingSelf:
				#print "isIntersectingWithinLists"
				self.addGcodeFromPerimeterPathsToGcode(layer, isIntersectingSelf, centerOutset.center, alreadyFilledArounds, halfWidth, rotatedLoopLayer)
			else:
				layer.addBoundaryPerimeter(centerOutset.center)
			addAlreadyFilledArounds(alreadyFilledArounds, centerOutset.center, self.overlapRemovalWidth)
			
	def addGcodeFromPerimeterPathsToGcode(self, layer, isIntersectingSelf, loop, loopLists, radius, rotatedLoopLayer):
		"Add the perimeter paths to the output."
		segments = []
		outlines = []
		thickOutlines = []
		allLoopLists = loopLists[:] + [thickOutlines]
		aroundLists = loopLists
		for pointIndex in xrange(len(loop)):
			pointBegin = loop[pointIndex]
			pointEnd = loop[(pointIndex + 1) % len(loop)]
			if isIntersectingSelf:
				if euclidean.isLineIntersectingLoops(outlines, pointBegin, pointEnd):
					segments += getSegmentsFromLoopListsPoints(allLoopLists, pointBegin, pointEnd)
				else:
					segments += getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd)
				addSegmentOutline(False, outlines, pointBegin, pointEnd, self.overlapRemovalWidth)
				addSegmentOutline(True, thickOutlines, pointBegin, pointEnd, self.overlapRemovalWidth)
			else:
				segments += getSegmentsFromLoopListsPoints(loopLists, pointBegin, pointEnd)
		perimeterPaths = []
		path = []
		muchSmallerThanRadius = 0.1 * radius
		segments = getInteriorSegments(rotatedLoopLayer.loops, segments)
		for segment in segments:
			pointBegin = segment[0].point
			if not isCloseToLast(perimeterPaths, pointBegin, muchSmallerThanRadius):
				path = [pointBegin]
				perimeterPaths.append(path)
			path.append(segment[1].point)
		if len(perimeterPaths) > 1:
			firstPath = perimeterPaths[0]
			lastPath = perimeterPaths[-1]
			if abs(lastPath[-1] - firstPath[0]) < 0.1 * muchSmallerThanRadius:
				connectedBeginning = lastPath[:-1] + firstPath
				perimeterPaths[0] = connectedBeginning
				perimeterPaths.remove(lastPath)
		muchGreaterThanRadius = 6.0 * radius
		for perimeterPath in perimeterPaths:
			if euclidean.getPathLength(perimeterPath) > muchGreaterThanRadius:
				layer.addGcodeFromThread(perimeterPath)
			
	def getCraftedGcode(self, gcodeText):
		"Parse gcodeCodec text and store the bevel gcodeCodec."
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
			
		for rotatedLoopLayer in self.gcode.rotatedLoopLayers:
			self.addInsetToGcode(rotatedLoopLayer)
			
		return self.gcodeCodec.output.getvalue()

	def parseInitialization(self):
		'Parse gcodeCodec initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcodeCodec.parseSplitLine(firstWord, splitLine)
			if firstWord == '(<decimalPlacesCarried>':
				#self.addInitializationToOutput()
				self.gcodeCodec.addTagBracketedLine(
					'bridgeWidthMultiplier', self.gcodeCodec.getRounded(self.bridgeWidthMultiplier))
			elif firstWord == '(</extruderInitialization>)':
				self.gcodeCodec.addTagBracketedLine('procedureName', name)
				return
			#elif firstWord == '(<layerThickness>':
				#self.layerThickness = float(splitLine[1])
			elif firstWord == '(<perimeterWidth>':
				#self.perimeterWidth = float(splitLine[1])
				#self.halfPerimeterWidth = 0.5 * self.perimeterWidth
				#self.overlapRemovalWidth = self.perimeterWidth * (0.7853) * self.overlapRemovalWidthOverPerimeterWidth
				self.gcodeCodec.addTagBracketedLine('nozzleDiameter', self.nozzleDiameter)
			self.gcodeCodec.addLine(line)

	def parseLine(self, line):
		"Parse a gcodeCodec line and add it to the inset skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == '(<boundaryPoint>':
			location = gcodec.getLocationFromSplitLine(None, splitLine)
			self.boundary.append(location.dropAxis())
		elif firstWord == '(<bridgeRotation>':
			secondWordWithoutBrackets = splitLine[1].replace('(', '').replace(')', '')
			self.rotatedLoopLayer.rotation = complex(secondWordWithoutBrackets)
		elif firstWord == '(<layer>':
			self.rotatedLoopLayer = euclidean.RotatedLoopLayer(float(splitLine[1]))
			self.gcodeCodec.addLine(line)
		elif firstWord == '(</layer>)':
			self.addInset(self.rotatedLoopLayer)
			self.rotatedLoopLayer = None
		elif firstWord == '(<nestedRing>)':
			self.boundary = []
			self.rotatedLoopLayer.loops.append(self.boundary)
		if self.rotatedLoopLayer == None:
			self.gcodeCodec.addLine(line)