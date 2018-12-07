#!/usr/bin/python

import os,sys,time,math,fnmatch
parent = os.path.dirname(os.getcwd())
sys.path.append(parent)
from array import array
from weights import *
from utils import *
from ROOT import *
start_time = time.time()

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Run as:
# > python modifyBinning.py
# 
# Optional arguments:
# -- statistical uncertainty threshold
#
# Notes:
# -- Finds certain root files in a given directory and rebins all histograms in each file
# -- A selection of subset of files in the input directory can be done below under "#Setup the selection ..."
# -- A custom binning choice can also be given by manually filling "xbinsList[chn]" for each channel
#    with the preferred choice of binning
# -- If no rebinning is wanted, but want to add PDF and R/F uncertainties, use a stat unc threshold 
#    that is larger than 100% (i.e, >1.)
# -- If CR and SR templates are in the same file and single bins are required for CR templates,
#    this can be done with "singleBinCR" bool (assumes that the CR templates contain "isCR" tags!).
# -- Use "removalKeys" to remove specific systematics from the output file.
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

iPlot='zpMass'
lumi='15000p0fbinv'
if len(sys.argv)>1: iPlot=str(sys.argv[1])
cutString = ''
templateDir = os.getcwd()+'/templates_alljets_halveStatUnc_2018_10_31/'+cutString
combinefile = 'templates_'+iPlot+'_'+lumi+'.root'

quiet = True #if you don't want to see the warnings that are mostly from the stat. shape algorithm!
rebinCombine = False #else rebins theta templates
doStatShapes = False
normalizeRENORM = True #only for signals
normalizePDF    = True #only for signals
#X53X53, TT, BB, HTB, etc --> this is used to identify signal histograms for combine templates when normalizing the pdf and muRF shapes to nominal!!!!
sigName = 'Zp' #MAKE SURE THIS WORKS FOR YOUR ANALYSIS PROPERLY!!!!!!!!!!!
massList = range(4000,12000+1,2000)
if 'kinematics_PS' in templateDir: massList = [1000,1300]
sigProcList = [sigName+'M'+str(mass) for mass in massList]
sigBinMax = {
sigName+'M2000':3000,sigName+'M4000':5500,sigName+'M6000':8000,sigName+'M8000':10000,sigName+'M10000':10000,sigName+'M12000':10000
}
#bkgProcList = ['ttbar','sitop','wjets','zjets','dibos','qcd'] #put the most dominant process first
#bkgProcList = ['top','ewk','qcd'] #put the most dominant process first
bkgProcList = ['ttbar','qcd']
era = "13TeV"

minNbins=1 #min number of bins to be merged
stat = 0.1 #statistical uncertainty requirement (enter >1.0 for no rebinning; i.g., "1.1")
statThres = 0.05 #statistical uncertainty threshold on total background to assign BB nuisances -- enter 0.0 to assign BB for all bins
#if len(sys.argv)>1: stat=float(sys.argv[1])
singleBinCR = False
symmetrizeTopPtShift = False
isEMlist = ['E']#,'M']
if iPlot=='minMlb': minNbins=3 #min 15GeV bin width
if iPlot=='HT' or iPlot=='ST': minNbins=8 #min 40GeV bin width

if rebinCombine:
	dataName = 'data_obs'
	upTag = 'Up'
	downTag = 'Down'
else: #theta
	dataName = 'DATA'
	upTag = '__plus'
	downTag = '__minus'

addShapes = False
lumiSys = 0.01 #lumi uncertainty
elIdIsoSys = 0.01 #electron id/iso uncertainty
muIdIsoSys = 0.005 #muon id/iso uncertainty
jesSys = 0.035 #JES uncertainty
jerSys = 0.03 #JER uncertainty
btagSys = 0.0#5 #b-tagging uncertainty
ttagSys = 0.05 #t-tagging uncertainty
puSys = 0.0#3 #Pileup uncertainty
pdfSys = 0.024 #PDF uncertainty
murfSys = 0.0 #Renorm/Fact. scale uncertainty
elcorrdSys = math.sqrt(lumiSys**2+elIdIsoSys**2+jesSys**2+jerSys**2+btagSys**2+ttagSys**2+puSys**2+pdfSys**2+murfSys**2)
mucorrdSys = math.sqrt(lumiSys**2+muIdIsoSys**2+jesSys**2+jerSys**2+btagSys**2+ttagSys**2+puSys**2+pdfSys**2+murfSys**2)

modelingSys = {}
modelingSys['ttbar'] = math.sqrt(0.03**2+0.04**2) #ttbar x-sec and muRF uncertainty
modelingSys['sitop'] = 0.06 #Single top x-sec uncertainty
modelingSys['wjets'] = math.sqrt(0.03**2+0.03**2) #W+jets x-sec and muRF uncertainty
modelingSys['zjets'] = 0.06 #Z+jets x-sec uncertainty
modelingSys['dibos'] = 0.06 #Diboson x-sec uncertainty
modelingSys['qcd']   = 0.06 #QCD x-sec uncertainty
modelingSys['other'] = math.sqrt(modelingSys['sitop']**2+modelingSys['wjets']**2+modelingSys['zjets']**2+modelingSys['dibos']**2+modelingSys['qcd']**2)
modelingSys[dataName]= 0.0

removalKeys = {} # True == keep, False == remove
removalKeys['jsf__'] = False
removalKeys['q2__']  = False

def findfiles(path, filtre):
    for root, dirs, files in os.walk(path):
        for f in fnmatch.filter(files, filtre):
            yield os.path.join(root, f)

#Setup the selection of the files to be rebinned: 
rfiles = []         
for file in findfiles(templateDir, '*.root'):
	if 'rebinned' in file or combinefile in file or '_'+iPlot+'_' not in file.split('/')[-1]: continue
	if lumi not in file: continue
	if not any([signal in file for signal in sigProcList]): continue
	rfiles.append(file)
if rebinCombine: rfiles = [templateDir+'/'+combinefile]

tfile = TFile(rfiles[0])
datahists = [k.GetName() for k in tfile.GetListOfKeys() if '__'+dataName in k.GetName()]
channels = [hist[hist.find('fbinv_')+6:hist.find('__')] for hist in datahists if 'isL_' not in hist]
allhists = {chn:[hist.GetName() for hist in tfile.GetListOfKeys() if chn+'__' in hist.GetName()] for chn in channels}

totBkgHists = {}
dataHists_ = {}
for hist in datahists:
	channel = hist[hist.find('fbinv_')+6:hist.find('__')]
	totBkgHists[channel]=tfile.Get(hist.replace('__'+dataName,'__'+bkgProcList[0])).Clone()
	dataHists_[channel]=tfile.Get(hist).Clone()
	for proc in bkgProcList:
		if proc==bkgProcList[0]: continue
		try: totBkgHists[channel].Add(tfile.Get(hist.replace('__'+dataName,'__'+proc)))
		except: 
			print "Missing",proc,"for category:",hist
			print "WARNING! Skipping this process!!!!"
			pass

xbinsListTemp = {}
for chn in totBkgHists.keys():
	if 'is'+isEMlist[0] not in chn: continue
	xbinsListTemp[chn]=[totBkgHists[chn].GetXaxis().GetBinUpEdge(totBkgHists[chn].GetXaxis().GetNbins())]
	Nbins = totBkgHists[chn].GetNbinsX()
	if stat>1.0:
		xbinsListTemp[chn] = [totBkgHists[chn].GetXaxis().GetBinUpEdge(totBkgHists[chn].GetXaxis().GetNbins())]
		for iBin in range(1,Nbins+1): 
			xbinsListTemp[chn].append(totBkgHists[chn].GetXaxis().GetBinLowEdge(Nbins+1-iBin))
		if len(isEMlist)>1: xbinsListTemp[chn.replace('is'+isEMlist[0],'is'+isEMlist[1])] = xbinsListTemp[chn]
	else:
		totTempBinContent_E = 0.
		totTempBinErrSquared_E = 0.
		totDataTempBinContent_E = 0.
		totDataTempBinErrSquared_E = 0.
		nBinsMerged = 0
		for iBin in range(1,Nbins+1):
			totTempBinContent_E += totBkgHists[chn].GetBinContent(Nbins+1-iBin)
			totTempBinErrSquared_E += totBkgHists[chn].GetBinError(Nbins+1-iBin)**2
			totDataTempBinContent_E += dataHists_[chn].GetBinContent(Nbins+1-iBin)
			totDataTempBinErrSquared_E += dataHists_[chn].GetBinError(Nbins+1-iBin)**2
			nBinsMerged+=1
			if nBinsMerged<minNbins: continue
			if totTempBinContent_E>0.:
				if math.sqrt(totTempBinErrSquared_E)/totTempBinContent_E<=stat:
					#if totDataTempBinContent_E==0. or totDataTempBinContent_M==0.: continue
					#if math.sqrt(totDataTempBinErrSquared_E)/totDataTempBinContent_E>0.45 or math.sqrt(totDataTempBinErrSquared_M)/totDataTempBinContent_M>0.45: continue
					totTempBinContent_E = 0.
					totTempBinErrSquared_E = 0.
					totDataTempBinContent_E = 0.
					totDataTempBinErrSquared_E = 0.
					nBinsMerged=0
					xbinsListTemp[chn].append(totBkgHists[chn].GetXaxis().GetBinLowEdge(Nbins+1-iBin))
		if xbinsListTemp[chn][-1]!=totBkgHists[chn].GetXaxis().GetBinLowEdge(1): xbinsListTemp[chn].append(totBkgHists[chn].GetXaxis().GetBinLowEdge(1))
		if totBkgHists[chn].GetBinContent(1)==0.: 
			if len(xbinsListTemp[chn])>2: del xbinsListTemp[chn][-2]
		elif totBkgHists[chn].GetBinError(1)/totBkgHists[chn].GetBinContent(1)>stat: 
			if len(xbinsListTemp[chn])>2: del xbinsListTemp[chn][-2]

print "==> Here is the binning I found with",stat*100,"% uncertainty threshold: "
print "//"*40
xbinsList = {}
xbinsList_ = {}
for chn in xbinsListTemp.keys():
	xbinsList_[chn] = []
	for bin in range(len(xbinsListTemp[chn])): xbinsList_[chn].append(xbinsListTemp[chn][len(xbinsListTemp[chn])-1-bin])
	if 'isCR' in chn and singleBinCR: xbinsList_[chn] = [xbinsList_[chn][0],xbinsList_[chn][-1]]
	print chn,"=",xbinsList_[chn]
print "//"*40

xbins = {}
for key in xbinsList_.keys(): xbins[key] = array('d', xbinsList_[key])

#os._exit(1)

iRfile=0
yieldsAll = {}
yieldsErrsAll = {}
nBBnuis = {}
nBBnuis['bkg'] = 0
for sig in sigProcList: nBBnuis[sig] = 0
for rfile in rfiles: 
	print "REBINNING FILE:",rfile
	tfiles = {}
	outputRfiles = {}
	tfiles[iRfile] = TFile(rfile)	
	outputRfiles[iRfile] = TFile(rfile.replace('.root','_rebinned_stat'+str(stat).replace('.','p')+'.root'),'RECREATE')

	print "PROGRESS:"
	for chn in channels:
		print "         ",chn
		if stat>1.0:
			themass = sigBinMax[sigName+rfile.split(sigName)[-1].split('_')[0]]
			xbinsList[chn] = xbinsList_[chn][:findidx_nearest(xbinsList_[chn],themass)+1]+[xbinsList_[chn][-1]] #= xbinsList[chn]
			if xbinsList[chn][-1]==xbinsList[chn][-2]: del xbinsList[chn][-2]
			xbins[chn] = array('d', xbinsList[chn])
		else: xbinsList[chn] = xbinsList_[chn]
		#print xbinsList[chn]
		#del xbinsList[chn][1]
		#del xbinsList[chn][1]
		print xbinsList[chn]
		rebinnedHists = {}
		#Rebinning histograms
		for hist in allhists[chn]:
			print hist
			rebinnedHists[hist]=tfiles[iRfile].Get(hist).Rebin(len(xbins[chn])-1,hist,xbins[chn])
			rebinnedHists[hist].SetDirectory(0)
			overflow(rebinnedHists[hist])
			if 'sig__mu' in hist and normalizeRENORM: #normalize the renorm/fact shapes to nominal
				renormNomHist = tfiles[iRfile].Get(hist[:hist.find('__mu')]).Clone()
				renormSysHist = tfiles[iRfile].Get(hist).Clone()
				rebinnedHists[hist].Scale(renormNomHist.Integral()/renormSysHist.Integral())
			if 'sig__pdf' in hist and normalizePDF: #normalize the pdf shapes to nominal
				renormNomHist = tfiles[iRfile].Get(hist[:hist.find('__pdf')]).Clone()
				renormSysHist = tfiles[iRfile].Get(hist).Clone()
				rebinnedHists[hist].Scale(renormNomHist.Integral()/renormSysHist.Integral())
			if '__pdf' in hist:
				if upTag not in hist or downTag not in hist: continue
			if '__mu' in hist: continue
			if any([item in hist and not removalKeys[item] for item in removalKeys.keys()]): continue
			if '__toppt'+downTag in hist and symmetrizeTopPtShift:
				for ibin in range(1, rebinnedHists[hist].GetNbinsX()+1):
					rebinnedHists[hist].SetBinContent(ibin, 2.*rebinnedHists[hist.replace('__toppt'+downTag,'')].GetBinContent(ibin)-rebinnedHists[hist.replace('__toppt'+downTag,'__toppt'+upTag)].GetBinContent(ibin))
			rebinnedHists[hist].Write()
			if '__trigeff' in hist:
				if 'isE' in hist: 
					newEname = rebinnedHists[hist].GetName().replace('__trigeff','__eltrigeff')
					rebinnedHists[newEname] = rebinnedHists[hist].Clone(newEname)
					rebinnedHists[newEname].Write()
				if 'isM' in hist:
					newMname = rebinnedHists[hist].GetName().replace('__trigeff','__mutrigeff')
					rebinnedHists[newMname] = rebinnedHists[hist].Clone(newMname)
					rebinnedHists[newMname].Write()
			yieldHistName = hist
			if not rebinCombine: yieldHistName = hist.replace('_sig','_'+rfile.split('_')[-2])
			yieldsAll[yieldHistName] = rebinnedHists[hist].Integral()
			yieldsErrsAll[yieldHistName] = 0.
			for ibin in range(1,rebinnedHists[hist].GetXaxis().GetNbins()+1):
				yieldsErrsAll[yieldHistName] += rebinnedHists[hist].GetBinError(ibin)**2
			yieldsErrsAll[yieldHistName] = math.sqrt(yieldsErrsAll[yieldHistName])

		#add statistical uncertainty shapes:
		if rebinCombine and doStatShapes:
			chnHistName = [hist for hist in datahists if chn in hist][0]
			rebinnedHists['chnTotBkgHist'] = rebinnedHists[chnHistName.replace(dataName,bkgProcList[0])].Clone()
			for bkg in bkgProcList:
				if bkg!=bkgProcList[0]:rebinnedHists['chnTotBkgHist'].Add(rebinnedHists[chnHistName.replace(dataName,bkg)])
			for ibin in range(1, rebinnedHists['chnTotBkgHist'].GetNbinsX()+1):
				if rebinnedHists['chnTotBkgHist'].GetBinError(ibin)/rebinnedHists['chnTotBkgHist'].GetBinContent(ibin)<=statThres: continue
				if rebinnedHists['chnTotBkgHist'].GetNbinsX()==1:
					for bkg in bkgProcList:
						val = rebinnedHists[chnHistName.replace(dataName,bkg)].GetBinContent(ibin)
						if val==0:
							if not quiet: print "WARNING: "+bkg+" has zero content in "+chn+" channel and bin#"+str(ibin)+", is this what you expect??? I will not assign stat shape shifts for this proc and chn!!!"
							continue
						error = rebinnedHists[chnHistName.replace(dataName,bkg)].GetBinError(ibin)
						err_up_name = rebinnedHists[chnHistName.replace(dataName,bkg)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+bkg+"_bin_%iUp" % ibin
						err_dn_name = rebinnedHists[chnHistName.replace(dataName,bkg)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+bkg+"_bin_%iDown" % ibin
						rebinnedHists[err_up_name] = rebinnedHists[chnHistName.replace(dataName,bkg)].Clone(err_up_name)
						rebinnedHists[err_dn_name] = rebinnedHists[chnHistName.replace(dataName,bkg)].Clone(err_dn_name)
						rebinnedHists[err_up_name].SetBinContent(ibin, val + error)
						rebinnedHists[err_dn_name].SetBinContent(ibin, val - error)
						if val-error<0: negBinCorrection(rebinnedHists[err_dn_name])
						elif val-error==0:
							if not quiet: print "WARNING: "+bkg+" has zero down shift in "+chn+" channel and bin#"+str(ibin)+" (1 event). Setting down shift to (bin content)*0.001"
							rebinnedHists[err_dn_name].SetBinContent(ibin, val*0.001)
						rebinnedHists[err_up_name].Write()
						rebinnedHists[err_dn_name].Write()
						nBBnuis['bkg']+=1
				else:
					dominantBkgProc = bkgProcList[0]
					val = rebinnedHists[chnHistName.replace(dataName,bkgProcList[0])].GetBinContent(ibin)
					for bkg in bkgProcList:
						if rebinnedHists[chnHistName.replace(dataName,bkg)].GetBinContent(ibin)>val: 
							val = rebinnedHists[chnHistName.replace(dataName,bkg)].GetBinContent(ibin)
							dominantBkgProc = bkg
					if val==0 and not quiet: print "WARNING: The most dominant bkg proc "+dominantBkgProc+" has zero content in "+chn+" channel and bin#"+str(ibin)+". Something is wrong!!!"
					error = rebinnedHists['chnTotBkgHist'].GetBinError(ibin)
					err_up_name = rebinnedHists[chnHistName.replace(dataName,dominantBkgProc)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+dominantBkgProc+"_bin_%iUp" % ibin
					err_dn_name = rebinnedHists[chnHistName.replace(dataName,dominantBkgProc)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+dominantBkgProc+"_bin_%iDown" % ibin
					rebinnedHists[err_up_name] = rebinnedHists[chnHistName.replace(dataName,dominantBkgProc)].Clone(err_up_name)
					rebinnedHists[err_dn_name] = rebinnedHists[chnHistName.replace(dataName,dominantBkgProc)].Clone(err_dn_name)
					rebinnedHists[err_up_name].SetBinContent(ibin, val + error)
					rebinnedHists[err_dn_name].SetBinContent(ibin, val - error)
					if val-error<0: negBinCorrection(rebinnedHists[err_dn_name])
					rebinnedHists[err_up_name].Write()
					rebinnedHists[err_dn_name].Write()
					nBBnuis['bkg']+=1
				for sig in sigProcList:
					sigNameNoMass = sigName
					if 'left' in sig: sigNameNoMass = sigName+'left'
					if 'right' in sig: sigNameNoMass = sigName+'right'
					val = rebinnedHists[chnHistName.replace(dataName,sig)].GetBinContent(ibin)
					if val==0: #This is not a sensitive bin, so no need for stat shape??
						if not quiet: print "WARNING: "+sig+" has zero content in "+chn+" channel and bin#"+str(ibin)+". I won't assign shape shifts for this bin!!!"
						continue
					error = rebinnedHists[chnHistName.replace(dataName,sig)].GetBinError(ibin)
					if error/val<=statThres: continue
					err_up_name = rebinnedHists[chnHistName.replace(dataName,sig)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+sigNameNoMass+"_bin_%iUp" % ibin
					err_dn_name = rebinnedHists[chnHistName.replace(dataName,sig)].GetName()+'__CMS_'+sigName+'_'+chn+'_'+era+'_'+sigNameNoMass+"_bin_%iDown" % ibin
					rebinnedHists[err_up_name] = rebinnedHists[chnHistName.replace(dataName,sig)].Clone(err_up_name)
					rebinnedHists[err_dn_name] = rebinnedHists[chnHistName.replace(dataName,sig)].Clone(err_dn_name)
					rebinnedHists[err_up_name].SetBinContent(ibin, val + error)
					rebinnedHists[err_dn_name].SetBinContent(ibin, val - error)
					if val-error<0: negBinCorrection(rebinnedHists[err_dn_name])
					rebinnedHists[err_up_name].Write()
					rebinnedHists[err_dn_name].Write()
					nBBnuis[sig]+=1
								
		#Constructing muRF shapes
		muRUphists = [k.GetName() for k in tfiles[iRfile].GetListOfKeys() if 'muR'+upTag in k.GetName() and chn in k.GetName()]
		newMuRFName = 'muRFcorrdNew'
		for hist in muRUphists:
			proc_ = hist.split('__')[1]
			muRFcorrdNewUpHist = rebinnedHists[hist].Clone(hist.replace('muR'+upTag,newMuRFName+upTag))
			muRFcorrdNewDnHist = rebinnedHists[hist].Clone(hist.replace('muR'+upTag,newMuRFName+downTag))
			histList = [
				rebinnedHists[hist[:hist.find('__mu')]], #nominal
				rebinnedHists[hist], #renormWeights[4]
				rebinnedHists[hist.replace('muR'+upTag,'muR'+downTag)], #renormWeights[2]
				rebinnedHists[hist.replace('muR'+upTag,'muF'+upTag)], #renormWeights[1]
				rebinnedHists[hist.replace('muR'+upTag,'muF'+downTag)], #renormWeights[0]
				rebinnedHists[hist.replace('muR'+upTag,'muRFcorrd'+upTag)], #renormWeights[5]
				rebinnedHists[hist.replace('muR'+upTag,'muRFcorrd'+downTag)] #renormWeights[3]
				]
			for ibin in range(1,histList[0].GetNbinsX()+1):
				weightList = [histList[ind].GetBinContent(ibin) for ind in range(len(histList))]
				indCorrdUp = weightList.index(max(weightList))
				indCorrdDn = weightList.index(min(weightList))

				muRFcorrdNewUpHist.SetBinContent(ibin,histList[indCorrdUp].GetBinContent(ibin))
				muRFcorrdNewDnHist.SetBinContent(ibin,histList[indCorrdDn].GetBinContent(ibin))

				muRFcorrdNewUpHist.SetBinError(ibin,histList[indCorrdUp].GetBinError(ibin))
				muRFcorrdNewDnHist.SetBinError(ibin,histList[indCorrdDn].GetBinError(ibin))
			if ('sig__mu' in hist and normalizeRENORM) or (rebinCombine and '__'+sigName in hist and '__mu' in hist and normalizeRENORM): #normalize the renorm/fact shapes to nominal
				nominalInt = rebinnedHists[hist[:hist.find('__mu')]].Integral()
				muRFcorrdNewUpHist.Scale(nominalInt/muRFcorrdNewUpHist.Integral())
				muRFcorrdNewDnHist.Scale(nominalInt/muRFcorrdNewDnHist.Integral())
			muRFcorrdNewUpHist.Write()
			muRFcorrdNewDnHist.Write()
			yieldsAll[muRFcorrdNewUpHist.GetName().replace('_sig','_'+rfile.split('_')[-2])] = muRFcorrdNewUpHist.Integral()
			yieldsAll[muRFcorrdNewDnHist.GetName().replace('_sig','_'+rfile.split('_')[-2])] = muRFcorrdNewDnHist.Integral()
			#Decorrelate muRF systematic ("muRFcorrdNew" still need to be removed in doThetaLimits.py!):
			muRFcorrdNewUpHist2 = muRFcorrdNewUpHist.Clone(hist.replace('muR'+upTag,proc_+newMuRFName+upTag))
			muRFcorrdNewDnHist2 = muRFcorrdNewDnHist.Clone(hist.replace('muR'+upTag,proc_+newMuRFName+downTag))
			muRFcorrdNewUpHist2.Write()
			muRFcorrdNewDnHist2.Write()

		#Constructing PDF shapes
		pdfUphists = [k.GetName() for k in tfiles[iRfile].GetListOfKeys() if 'pdf0' in k.GetName() and chn in k.GetName()]
		newPDFName = 'pdfNew'
		for hist in pdfUphists:
			pdfNewUpHist = rebinnedHists[hist].Clone(hist.replace('pdf0',newPDFName+upTag))
			pdfNewDnHist = rebinnedHists[hist].Clone(hist.replace('pdf0',newPDFName+downTag))
			for ibin in range(1,pdfNewUpHist.GetNbinsX()+1):
				weightList = [rebinnedHists[hist.replace('pdf0','pdf'+str(pdfInd))].GetBinContent(ibin) for pdfInd in range(100)]
				indPDFUp = sorted(range(len(weightList)), key=lambda k: weightList[k])[83]
				indPDFDn = sorted(range(len(weightList)), key=lambda k: weightList[k])[15]
				pdfNewUpHist.SetBinContent(ibin,rebinnedHists[hist.replace('pdf0','pdf'+str(indPDFUp))].GetBinContent(ibin))
				pdfNewDnHist.SetBinContent(ibin,rebinnedHists[hist.replace('pdf0','pdf'+str(indPDFDn))].GetBinContent(ibin))
				pdfNewUpHist.SetBinError(ibin,rebinnedHists[hist.replace('pdf0','pdf'+str(indPDFUp))].GetBinError(ibin))
				pdfNewDnHist.SetBinError(ibin,rebinnedHists[hist.replace('pdf0','pdf'+str(indPDFDn))].GetBinError(ibin))
			if ('sig__pdf' in hist and normalizePDF) or (rebinCombine and '__'+sigName in hist and '__pdf' in hist and normalizePDF): #normalize the renorm/fact shapes to nominal
				nominalInt = rebinnedHists[hist[:hist.find('__pdf')]].Integral()
				pdfNewUpHist.Scale(nominalInt/pdfNewUpHist.Integral())
				pdfNewDnHist.Scale(nominalInt/pdfNewDnHist.Integral())
			pdfNewUpHist.Write()
			pdfNewDnHist.Write()
			yieldsAll[pdfNewUpHist.GetName().replace('_sig','_'+rfile.split('_')[-2])] = pdfNewUpHist.Integral()
			yieldsAll[pdfNewDnHist.GetName().replace('_sig','_'+rfile.split('_')[-2])] = pdfNewDnHist.Integral()
			
	tfiles[iRfile].Close()
	outputRfiles[iRfile].Close()
	iRfile+=1
tfile.Close()
print ">> Rebinning Done!"
print "===>>> Number of BB nuisances added:"
print "                                    bkg:",nBBnuis['bkg']
for sig in sigProcList: print "                                    "+sig+":",nBBnuis[sig]
	
isEMlist =[]
nttaglist=[]
nWtaglist=[]
nbtaglist=[]
njetslist=[]
for chn in channels:
	tagind = 0
	if chn.split('_')[tagind+rebinCombine] not in isEMlist: 
		isEMlist.append(chn.split('_')[tagind+rebinCombine])
	if chn.split('_')[tagind+rebinCombine] not in nttaglist and '_nT' in chn: 
		tagind += 1
		nttaglist.append(chn.split('_')[tagind+rebinCombine])
	if chn.split('_')[tagind+rebinCombine] not in nWtaglist and '_nW' in chn: 
		tagind += 1
		nWtaglist.append(chn.split('_')[tagind+rebinCombine])
	if chn.split('_')[tagind+rebinCombine] not in nbtaglist and '_nB' in chn: 
		tagind += 1
		nbtaglist.append(chn.split('_')[tagind+rebinCombine])
	if chn.split('_')[tagind+rebinCombine] not in njetslist and '_nJ' in chn: 
		tagind += 1
		njetslist.append(chn.split('_')[tagind+rebinCombine])
if len(nttaglist)==0: nttaglist=['0p']
if len(nWtaglist)==0: nWtaglist=['0p']
if len(nbtaglist)==0: nbtaglist=['0p']
if len(njetslist)==0: njetslist=['0p']

procNames={
           'top':'TOP',
           'ttbar':'TT',
           'sitop':'Single top',
           'ewk':'EW',
           'wjets':'W+jets',
           'zjets':'Z+jets',
           'dibos':'WW',
           'qcd':'QCD',
           'other':'Other',
           'DATA':'Data',
           'data_obs':'Data',
           'totBkg':'Total bkg.',
           'dataOverBkg':'Data/Bkg',
           }
for sig in sigProcList: 
	if 'left' in sig:  procNames[sig]='LH \\xft ('+str(float(sig[7:-4])/1000)+' \\TeV)'
	if 'right' in sig: procNames[sig]='RH \\xft ('+str(float(sig[7:-5])/1000)+' \\TeV)'
	procNames[sig]='RSG ('+str(float(sig[len(sigName)+1:])/1000)+'\\TeV)'

print "List of systematics for "+bkgProcList[0]+" process and "+channels[0]+" channel:"
print "        ",sorted([hist[hist.find(bkgProcList[0]+'__')+len(bkgProcList[0])+2:hist.find(upTag)] for hist in yieldsAll.keys() if channels[0] in hist and '__'+bkgProcList[0]+'__' in hist and upTag in hist])# and 'muRF' not in hist

def getShapeSystUnc(proc,chn):
	if not addShapes: return 0
	systematicList = sorted([hist[hist.find(proc+'__')+len(proc)+2:hist.find(upTag)] for hist in yieldsAll.keys() if chn in hist and '__'+proc+'__' in hist and upTag in hist])# and 'muRF' not in hist
	totUpShiftPrctg=0
	totDnShiftPrctg=0
	histoPrefix = allhists[chn][0][:allhists[chn][0].find('__')+2]
	nomHist = histoPrefix+proc
	for syst in systematicList:
		for ud in [upTag,downTag]:
			shpHist = histoPrefix+proc+'__'+syst+ud
			shift = yieldsAll[shpHist]/(yieldsAll[nomHist]+1e-20)-1
			if shift>0.: totUpShiftPrctg+=shift**2
			if shift<0.: totDnShiftPrctg+=shift**2
	shpSystUncPrctg = (math.sqrt(totUpShiftPrctg)+math.sqrt(totDnShiftPrctg))/2 #symmetrize the total shape uncertainty up/down shifts
	return shpSystUncPrctg	

table = []
for isEM in isEMlist:
	if isEM=='isE': corrdSys = elcorrdSys
	if isEM=='isM': corrdSys = mucorrdSys
	table.append(['break'])
	table.append(['',isEM+'_yields'])
	table.append(['break'])
	table.append(['YIELDS']+[chn for chn in channels if isEM in chn]+['\\\\'])
	for proc in bkgProcList+['totBkg',dataName,'dataOverBkg']+sigProcList:
		row = [procNames[proc]]
		for chn in channels:
			if isEM not in chn: continue
			modTag = chn[chn.find('nW'):]
			histoPrefix = allhists[chn][0][:allhists[chn][0].find('__')+2]
			yieldtemp = 0.
			yielderrtemp = 0.
			if proc=='totBkg' or proc=='dataOverBkg':
				for bkg in bkgProcList:
					try:
						yieldtemp += yieldsAll[histoPrefix+bkg]
						yielderrtemp += yieldsErrsAll[histoPrefix+bkg]**2
						yielderrtemp += (modelingSys[bkg]*yieldsAll[histoPrefix+bkg])**2
						yielderrtemp += (getShapeSystUnc(bkg,chn)*yieldsAll[histoPrefix+bkg])**2
					except:
						print "Missing",bkg,"for channel:",chn
						pass
				yielderrtemp += (corrdSys*yieldtemp)**2
				if proc=='dataOverBkg':
					dataTemp = yieldsAll[histoPrefix+dataName]+1e-20
					dataTempErr = yieldsErrsAll[histoPrefix+dataName]**2
					yielderrtemp = ((dataTemp/yieldtemp)**2)*(dataTempErr/dataTemp**2+yielderrtemp/yieldtemp**2)
					yieldtemp = dataTemp/yieldtemp
			else:
				try:
					yieldtemp += yieldsAll[histoPrefix+proc]
					yielderrtemp += yieldsErrsAll[histoPrefix+proc]**2
					yielderrtemp += (getShapeSystUnc(proc,chn)*yieldsAll[histoPrefix+proc])**2
				except:
					print "Missing",proc,"for channel:",chn
					pass
				if proc in sigProcList:
					signal=proc
					if 'left' in signal: signal=proc.replace('left','')+'left'
					if 'right' in signal: signal=proc.replace('right','')+'right'
					yieldtemp*=xsec[signal]
					yielderrtemp*=xsec[signal]**2
				else: yielderrtemp += (modelingSys[proc]*yieldtemp)**2
				yielderrtemp += (corrdSys*yieldtemp)**2
			yielderrtemp = math.sqrt(yielderrtemp)
			if proc==dataName: row.append(' & '+str(int(yieldsAll[histoPrefix+proc])))
			else: row.append(' & '+str(round_sig(yieldtemp,5))+' $\pm$ '+str(round_sig(yielderrtemp,2)))
		row.append('\\\\')
		table.append(row)
	iSig = 0
	for sig in sigProcList:
		#row=['SoverSqrtSpB_'+sig]
		row=['SoverSigmaB_'+sig]
		iChn = 1
		for chn in channels: 
			if isEM not in chn: continue
			bkgYld_ = float([iList for iList in table[table.index(['',isEM+'_yields']):] if iList[0] == procNames['totBkg']][0][iChn].strip().split()[1])
			bkgYldErr_ = float([iList for iList in table[table.index(['',isEM+'_yields']):] if iList[0] == procNames['totBkg']][0][iChn].strip().split()[3])
			sigYld_ = float([iList for iList in table[table.index(['',isEM+'_yields']):] if iList[0] == procNames[sig]][0][iChn].strip().split()[1])
			sigYldErr_ = float([iList for iList in table[table.index(['',isEM+'_yields']):] if iList[0] == procNames[sig]][0][iChn].strip().split()[3])
			#row.append(' & '+str(sigYld_/math.sqrt(sigYld_+bkgYld_)))
			row.append(' & '+str(round_sig(sigYld_/bkgYldErr_,5)))
			iChn+=1
		row.append('\\\\')
		table.append(row)
		iSig+=1
			
table.append(['break'])
table.append(['','isL_yields'])
table.append(['break'])
table.append(['YIELDS']+[chn.replace('isE','isL') for chn in channels if 'isE' in chn]+['\\\\'])
for proc in bkgProcList+['totBkg',dataName,'dataOverBkg']+sigProcList:
	row = [procNames[proc]]
	for chn in channels:
		if 'isE' not in chn: continue
		modTag = chn[chn.find('nW'):]
		histoPrefixE = allhists[chn][0][:allhists[chn][0].find('__')+2]
		histoPrefixM = histoPrefixE.replace('isE','isM')
		yieldtemp = 0.
		yieldtempE = 0.
		yieldtempM = 0.
		yielderrtemp = 0. 
		if proc=='totBkg' or proc=='dataOverBkg':
			for bkg in bkgProcList:
				yieldEplusMtemp = 0
				try:
					yieldtempE += yieldsAll[histoPrefixE+bkg]
					yieldtemp += yieldsAll[histoPrefixE+bkg]
					yieldEplusMtemp += yieldsAll[histoPrefixE+bkg]
					yielderrtemp += yieldsErrsAll[histoPrefixE+bkg]**2
					yielderrtemp += (getShapeSystUnc(bkg,chn)*yieldsAll[histoPrefixE+bkg])**2
				except:
					print "Missing",bkg,"for channel:",chn
					pass
				try:
					yieldtempM += yieldsAll[histoPrefixM+bkg]
					yieldtemp += yieldsAll[histoPrefixM+bkg]
					yieldEplusMtemp += yieldsAll[histoPrefixM+bkg]
					yielderrtemp += yieldsErrsAll[histoPrefixM+bkg]**2
					yielderrtemp += (getShapeSystUnc(bkg,chn.replace('isE','isM'))*yieldsAll[histoPrefixM+bkg])**2
				except:
					print "Missing",bkg,"for channel:",chn.replace('isE','isM')
					pass
				yielderrtemp += (modelingSys[bkg]*yieldEplusMtemp)**2 #(addSys*(Nelectron+Nmuon))**2 --> correlated across e/m
			yielderrtemp += (elcorrdSys*yieldtempE)**2+(mucorrdSys*yieldtempM)**2
			if proc=='dataOverBkg':
				dataTemp = yieldsAll[histoPrefixE+dataName]+yieldsAll[histoPrefixM+dataName]+1e-20
				dataTempErr = yieldsErrsAll[histoPrefixE+dataName]**2+yieldsErrsAll[histoPrefixM+dataName]**2
				yielderrtemp = ((dataTemp/yieldtemp)**2)*(dataTempErr/dataTemp**2+yielderrtemp/yieldtemp**2)
				yieldtemp = dataTemp/yieldtemp
		else:
			try:
				yieldtempE += yieldsAll[histoPrefixE+proc]
				yieldtemp  += yieldsAll[histoPrefixE+proc]
				yielderrtemp += yieldsErrsAll[histoPrefixE+proc]**2
				yielderrtemp += (getShapeSystUnc(proc,chn)*yieldsAll[histoPrefixE+proc])**2
			except:
				print "Missing",proc,"for channel:",chn
				pass
			try:
				yieldtempM += yieldsAll[histoPrefixM+proc]
				yieldtemp  += yieldsAll[histoPrefixM+proc]
				yielderrtemp += yieldsErrsAll[histoPrefixM+proc]**2
				yielderrtemp += (getShapeSystUnc(proc,chn.replace('isE','isM'))*yieldsAll[histoPrefixM+proc])**2
			except:
				print "Missing",proc,"for channel:",chn.replace('isE','isM')
				pass
			if proc in sigProcList:
				signal=proc
				if 'left' in signal: signal=proc.replace('left','')+'left'
				if 'right' in signal: signal=proc.replace('right','')+'right'
				yieldtempE*=xsec[signal]
				yieldtempM*=xsec[signal]
				yieldtemp*=xsec[signal]
				yielderrtemp*=xsec[signal]**2
			else: yielderrtemp += (modelingSys[proc]*yieldtemp)**2 #(addSys*(Nelectron+Nmuon))**2 --> correlated across e/m
			yielderrtemp += (elcorrdSys*yieldtempE)**2+(mucorrdSys*yieldtempM)**2
		yielderrtemp = math.sqrt(yielderrtemp)
		if proc==dataName: row.append(' & '+str(int(yieldsAll[histoPrefixE+proc]+yieldsAll[histoPrefixM+proc])))
		else: row.append(' & '+str(round_sig(yieldtemp,5))+' $\pm$ '+str(round_sig(yielderrtemp,2)))
	row.append('\\\\')
	table.append(row)
iSig=0
for sig in sigProcList:
	#row=['SoverSqrtSpB_'+sig]
	row=['SoverSigmaB_'+sig]
	iChn = 1
	for chn_ in channels: 
		if 'isE' not in chn_: continue
		chn = chn_.replace('isE','isL')
		bkgYld_ = float([iList for iList in table[table.index(['','isL_yields']):] if iList[0] == procNames['totBkg']][0][iChn].strip().split()[1])
		bkgYldErr_ = float([iList for iList in table[table.index(['','isL_yields']):] if iList[0] == procNames['totBkg']][0][iChn].strip().split()[3])
		sigYld_ = float([iList for iList in table[table.index(['','isL_yields']):] if iList[0] == procNames[sig]][0][iChn].strip().split()[1])
		sigYldErr_ = float([iList for iList in table[table.index(['','isL_yields']):] if iList[0] == procNames[sig]][0][iChn].strip().split()[3])
		#row.append(' & '+str(sigYld_/math.sqrt(sigYld_+bkgYld_)))
		row.append(' & '+str(round_sig(sigYld_/bkgYldErr_,5)))
		iChn+=1
	row.append('\\\\')
	table.append(row)
	iSig+=1

#systematics
table.append(['break'])
table.append(['','Systematics'])
table.append(['break'])
for proc in bkgProcList+sigProcList:
	table.append([proc]+[chn for chn in channels]+['\\\\'])
	systematicList = sorted([hist[hist.find(proc+'__')+len(proc)+2:hist.find(upTag)] for hist in yieldsAll.keys() if channels[0] in hist and '__'+proc+'__' in hist and upTag in hist])
	for syst in systematicList:
		for ud in [upTag,downTag]:
			row = [syst+ud]
			for chn in channels:
				histoPrefix = allhists[chn][0][:allhists[chn][0].find('__')+2]
				nomHist = histoPrefix+proc
				shpHist = histoPrefix+proc+'__'+syst+ud
				try: row.append(' & '+str(round(yieldsAll[shpHist]/(yieldsAll[nomHist]+1e-20),2)))
				except:
					print "Missing",proc,"for channel:",chn,"and systematic:",syst
					pass
			row.append('\\\\')
			table.append(row)
	row = ['stat']
	for chn in channels:
		histoPrefix = allhists[chn][0][:allhists[chn][0].find('__')+2]
		nomHist = histoPrefix+proc
		try: row.append(' & '+str(round(yieldsErrsAll[nomHist]/(yieldsAll[nomHist]+1e-20),2)))
		except:
			print "Missing",proc,"for channel:",chn,"and systematic: stat"
			pass
	row.append('\\\\')
	table.append(row)	
	table.append(['break'])

postFix = ''#'_noQ2'
if addShapes: postFix+='_addShps'
out=open(templateDir+'/'+combinefile.replace('templates','yields').replace('.root','_rebinned_stat'+str(stat).replace('.','p'))+postFix+'.txt','w')
printTable(table,out)
#os._exit(1)
print "       WRITING SUMMARY TEMPLATES: "
lumiStr = combinefile.split('_')[-1][:-7]
for signal in sigProcList:
	print "              ... "+signal
	yldRfileName = templateDir+'/templates_'+iPlot+'YLD_'+signal+'_'+lumiStr+'fbinv_rebinned_stat'+str(stat).replace('.','p')+'.root'
	yldRfile = TFile(yldRfileName,'RECREATE')
	for isEM in isEMlist:		
		for proc in bkgProcList+[dataName,signal]:
			yldHists = {}
			yldHists[isEM+proc]=TH1F(iPlot+'YLD_'+lumiStr+'fbinv_'+isEM+'_nT0p_nW0p_nB0p_nJ0p__'+proc.replace(signal,'sig').replace('data','DATA'),'',len(channels)/2,0,len(channels)/2)
			systematicList = sorted([hist[hist.find(proc)+len(proc)+2:hist.find(upTag)] for hist in yieldsAll.keys() if channels[0] in hist and '__'+proc+'__' in hist and upTag in hist])
			for syst in systematicList:
				for ud in [upTag,downTag]: yldHists[isEM+proc+syst+ud]=TH1F(iPlot+'YLD_'+lumiStr+'fbinv_'+isEM+'_nT0p_nW0p_nB0p_nJ0p__'+proc.replace(signal,'sig').replace('data','DATA')+'__'+syst+ud,'',len(channels)/2,0,len(channels)/2)
			ibin = 1
			for chn in channels:
				if isEM not in chn: continue
				binStr = ''
				if nttaglist[0]!='0p':
					nttag = chn[chn.find('_nT')+3:].split('_')[0]
					if 'p' in nttag: binStr+='#geq'+nttag[:-1]+'t/'
					else: binStr+=nttag+'t/'
				if nWtaglist[0]!='0p':
					nWtag = chn[chn.find('_nW')+3:].split('_')[0]
					if 'p' in nWtag: binStr+='#geq'+nWtag[:-1]+'W/'
					else: binStr+=nWtag+'W/'
				if nbtaglist[0]!='0p':
					nbtag = chn[chn.find('_nB')+3:].split('_')[0]
					if 'p' in nbtag: binStr+='#geq'+nbtag[:-1]+'b/'
					else: binStr+=nbtag+'b/'
				if njetslist[0]!='0p' and len(njetslist)>1:
					njets = chn[chn.find('_nJ')+3:].split('_')[0]
					if 'p' in njets: binStr+='#geq'+njets[:-1]+'j'
					else: binStr+=njets+'j'
				if binStr.endswith('/'): binStr=binStr[:-1]
				histoPrefix = allhists[chn][0][:allhists[chn][0].find('__')+2]
				try: 
					yldTemp = yieldsAll[histoPrefix+proc]
					yldErrTemp = yieldsErrsAll[histoPrefix+proc]
				except: 
					print "Missing "+proc+" for channel: "+chn+" (setting yield to zero!!!)"
					yldTemp = 0
					yldErrTemp = 0
				yldHists[isEM+proc].SetBinContent(ibin,yldTemp)
				yldHists[isEM+proc].SetBinError(ibin,yldErrTemp)
				yldHists[isEM+proc].GetXaxis().SetBinLabel(ibin,binStr)
				for syst in systematicList:
					for ud in [upTag,downTag]:
						try: yldTemp = yieldsAll[histoPrefix+proc+'__'+syst+ud]
						except: yldTemp = 0
						yldHists[isEM+proc+syst+ud].SetBinContent(ibin,yldTemp)
						yldHists[isEM+proc+syst+ud].GetXaxis().SetBinLabel(ibin,binStr)
				ibin+=1
			yldHists[isEM+proc].Write()
			for syst in systematicList:
				for ud in [upTag,downTag]: yldHists[isEM+proc+syst+ud].Write()
	yldRfile.Close()

print("--- %s minutes ---" % (round((time.time() - start_time)/60,2)))

