'''
D. Melgar 02/2014

Forward modeling routines
'''

def waveforms(home,project_name,rupture_name,station_file,model_name,run_name,integrate,tsunami,hot_start,resample,beta):
    '''
    This routine will take synthetics and apply a slip dsitribution. It will delay each 
    subfault by the appropriate rupture time and linearly superimpose all of them. Output
    will be one sac waveform file per direction of motion (NEU) for each station defined in the
    station_file. Depending on the specified rake angle at each subfault the code will compute 
    the contribution to dip and strike slip directions. It will also compute the moment at that
    subfault and scale it according to the unit amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
        integrate: =0 if you want output to be velocity, =1 if you want output to de displacement
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,allclose,vstack,deg2rad,array,sin,cos
    from obspy import read,Stream
    from string import rjust
    import datetime
    import gc
    
    print 'Solving for kinematic problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    logpath=home+project_name+'/logs/'
    log=''
    #Time for log file
    now=datetime.datetime.now()
    now=now.strftime('%b-%d-%H%M')
    #load source
    source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    stagps_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #What am I processing v or d ?
    if integrate==1:
        vord='disp'
    else:
        vord='vel'
    #Loop over stations
    for ksta in range(hot_start,len(staname)):
        print 'Working on station '+staname[ksta]+' ('+str(ksta+1)+'/'+str(len(staname))+')'
        #Initalize output
        n=Stream()
        e=Stream()
        z=Stream()
        sta=staname[ksta]
        #Loop over sources (Add delays)
        try:
            for k in range(source.shape[0]):
                if k%100==0:
                    print '... working on parameter '+str(k)+' of '+str(len(source))
                #Get subfault parameters
                nfault='subfault'+rjust(str(int(source[k,0])),4,'0')
                nsub='sub'+rjust(str(int(source[k,0])),4,'0')
                zs=source[k,3]
                ss_slip=source[k,8]
                ds_slip=source[k,9]
                #Rotate
                if beta != None:
                    beta_rot=deg2rad(beta)
                    R=array([[cos(beta_rot),sin(beta_rot)],[-sin(beta_rot),cos(beta_rot)]])
                    rot=R.dot(vstack((ss_slip,ds_slip)))
                    ss_slip=rot[0]
                    ds_slip=rot[1]
                rtime=source[k,12]
                #Where's the data
                strdepth='%.4f' % zs
                if tsunami==False: 
                    syn_path=home+project_name+'/GFs/dynamic/'+model_name+'_'+strdepth+'.'+nsub+'/'
                else:
                    syn_path=home+project_name+'/GFs/tsunami/'+model_name+'_'+strdepth+'.'+nsub+'/'
                #Get synthetics
                ess=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.e')
                nss=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.n')
                zss=read(syn_path+sta+'.'+nfault+'.SS.'+vord+'.z')
                eds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.e')
                nds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.n')
                zds=read(syn_path+sta+'.'+nfault+'.DS.'+vord+'.z')
                #Decide if resampling is required
                if resample!=None:
                    if resample < (1/ess[0].stats.delta): #Downsample
                        ess[0].resample(resample)
                        nss[0].resample(resample)
                        zss[0].resample(resample)
                        eds[0].resample(resample)
                        nds[0].resample(resample)
                        zds[0].resample(resample)
                    elif resample > (1/ess[0].stats.delta): #Upsample
                        upsample(ess,1./resample)
                        upsample(nss,1./resample)
                        upsample(zss,1./resample)
                        upsample(eds,1./resample)
                        upsample(nds,1./resample)
                        upsample(zds,1./resample)
                dt=ess[0].stats.delta
                #Time shift them according to subfault rupture time
                ess=tshift(ess,rtime)
                ess[0].stats.starttime=round_time(ess[0].stats.starttime,dt)
                nss=tshift(nss,rtime)
                nss[0].stats.starttime=round_time(nss[0].stats.starttime,dt)
                zss=tshift(zss,rtime)
                zss[0].stats.starttime=round_time(zss[0].stats.starttime,dt)
                eds=tshift(eds,rtime)
                eds[0].stats.starttime=round_time(eds[0].stats.starttime,dt)
                nds=tshift(nds,rtime)
                nds[0].stats.starttime=round_time(nds[0].stats.starttime,dt)
                zds=tshift(zds,rtime)
                zds[0].stats.starttime=round_time(zds[0].stats.starttime,dt)
                if allclose((ss_slip**2+ds_slip**2)**0.5,0)==False:  #Only add things that matter
                    log=log+nfault+', SS='+str(ss_slip)+', DS='+str(ds_slip)+'\n'
                    #A'ight, add 'em up
                    etotal=add_traces(ess,eds,ss_slip,ds_slip)
                    ntotal=add_traces(nss,nds,ss_slip,ds_slip)
                    ztotal=add_traces(zss,zds,ss_slip,ds_slip)
                    #Add to previous subfault's results
                    e=add_traces(e,etotal,1,1)
                    n=add_traces(n,ntotal,1,1)
                    z=add_traces(z,ztotal,1,1)
                else:
                    log=log+"No slip on subfault "+nfault+', ignoring it...\n'
                gc.collect()
            #Save results
            e.write(outpath+run_name+'.'+sta+'.'+vord+'.e',format='SAC')
            n.write(outpath+run_name+'.'+sta+'.'+vord+'.n',format='SAC')
            z.write(outpath+run_name+'.'+sta+'.'+vord+'.u',format='SAC')
        except:
            print 'An error coccured, skipping station'
    f=open(logpath+'waveforms.'+now+'.log','a')
    f.write(log)
    f.close()
        
        
        
def waveforms_matrix(home,project_name,fault_name,rupture_name,station_file,GF_list,
                model_name,run_name,epicenter,time_epi,integrate,tsunami,hot_start,
                resample,beta,rupture_speed,num_windows,dt,NFFT):
    '''
    To supplant waveforms() it needs to include resmapling and all that jazz...
    
    This routine will take synthetics and apply a slip dsitribution. It will delay each 
    subfault by the appropriate rupture time and linearly superimpose all of them. Output
    will be one sac waveform file per direction of motion (NEU) for each station defined in the
    station_file. Depending on the specified rake angle at each subfault the code will compute 
    the contribution to dip and strike slip directions. It will also compute the moment at that
    subfault and scale it according to the unit amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
        integrate: =0 if you want output to be velocity, =1 if you want output to de displacement
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,allclose,vstack,deg2rad,array,sin,cos,where,zeros,arange
    from obspy import read,Stream,Trace
    from string import rjust
    import datetime
    import gc
    from mudpy.inverse import getG
    from linecache import getline
    from os import remove
    
    print 'Solving for kinematic problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    logpath=home+project_name+'/logs/'
    log=''
    #Time for log file
    now=datetime.datetime.now()
    now=now.strftime('%b-%d-%H%M')
    #load source
    #source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    station_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #Now load rupture model
    mss=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=8)
    mds=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=9)
    m=zeros(2*len(mss))
    i=arange(0,2*len(mss),2)
    m[i]=mss
    i=arange(1,2*len(mds),2)
    m[i]=mds
    #What am I processing v or d ?
    if integrate==1:
        vord='disp'
    else:
        vord='vel'
    #Load gflist
    gfsta=genfromtxt(home+project_name+'/data/station_info/'+GF_list,usecols=0,skip_header=1,dtype='S6')
    #Loop over stations
    for ksta in range(hot_start,len(staname)):
        print 'Working on station '+staname[ksta]+' ('+str(ksta+1)+'/'+str(len(staname))+')'
        #Initalize output
        n=Stream()
        e=Stream()
        z=Stream()
        sta=staname[ksta]
        #Make dummy data
        ndummy=Stream(Trace())
        ndummy[0].data=zeros(int(NFFT))
        ndummy[0].stats.delta=dt
        ndummy[0].stats.starttime=time_epi
        edummy=ndummy.copy()
        udummy=ndummy.copy()
        ndummy.write(home+project_name+'/data/waveforms/'+sta+'.'+vord+'.n',format='SAC')
        edummy.write(home+project_name+'/data/waveforms/'+sta+'.'+vord+'.e',format='SAC')
        udummy.write(home+project_name+'/data/waveforms/'+sta+'.'+vord+'.u',format='SAC')
        #Extract only one station from GF_list file
        ista=int(where(gfsta==staname[ksta])[0])+2
        #Make mini GF_file
        tmpgf='tmpfwd.gflist'
        try:
            remove(home+project_name+'/data/station_info/'+tmpgf)
        except:
            pass
        gflist=getline(home+project_name+'/data/station_info/'+GF_list,ista)
        f=open(home+project_name+'/data/station_info/'+tmpgf,'w')
        f.write('# Headers\n')
        f.write(gflist)
        f.close()
        #Get matrix for one station to all sources
        G_from_file=False
        G_name='tmpfwd'
        G=getG(home,project_name,fault_name,model_name,tmpgf,G_from_file,G_name,epicenter,
                rupture_speed,num_windows,decimate=None,bandpass=None,tsunami=False)
        # Matrix multiply and separate data streams
        d=G.dot(m)
        n=ndummy.copy()
        e=edummy.copy()
        u=udummy.copy()
        ncut=len(d)/3
        n[0].data=d[0:ncut]
        e[0].data=d[ncut:2*ncut]
        u[0].data=d[2*ncut:3*ncut]
        # Write to file
        n.write(home+project_name+'/output/forward_models/'+run_name+'.'+gfsta[ksta]+'.'+vord+'.n',format='SAC')
        e.write(home+project_name+'/output/forward_models/'+run_name+'.'+gfsta[ksta]+'.'+vord+'.e',format='SAC')
        u.write(home+project_name+'/output/forward_models/'+run_name+'.'+gfsta[ksta]+'.'+vord+'.u',format='SAC')

        
def waveforms_fakequakes(home,project_name,fault_name,rupture_list,GF_list,
                model_name,run_name,dt,NFFT,G_from_file,G_name,source_time_function,
                stf_falloff_rate):
    '''
    To supplant waveforms_matrix() it needs to include resmapling and all that jazz...
    
    Instead of doing matrix multiplication one stations at a time, do it for all stations
    
    This routine will take synthetics and apply a slip dsitribution. It will delay each 
    subfault by the appropriate rupture time and linearly superimpose all of them. Output
    will be one sac waveform file per direction of motion (NEU) for each station defined in the
    station_file. Depending on the specified rake angle at each subfault the code will compute 
    the contribution to dip and strike slip directions. It will also compute the moment at that
    subfault and scale it according to the unit amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
        integrate: =0 if you want output to be velocity, =1 if you want output to de displacement
       
    OUT:
        Nothing
    '''
    from numpy import genfromtxt
    import datetime
    
    print 'Solving for kinematic problem(s)'
    #Time for log file
    now=datetime.datetime.now()
    now=now.strftime('%b-%d-%H%M')
    #load source names
    all_sources=genfromtxt(home+project_name+'/data/'+rupture_list,dtype='S')
    #Load all synthetics
    print '... loading all synthetics into memory'
    Nss,Ess,Zss,Nds,Eds,Zds=load_fakequakes_synthetics(home,project_name,fault_name,model_name,GF_list,G_from_file,G_name)
    print '... ... done'
    #Now loop over rupture models
    for ksource in range(len(all_sources)):
        print '... solving for source '+str(ksource)+' of '+str(len(all_sources))
        rupture_name=all_sources[ksource]
        #Get epicentral time
        epicenter,time_epi=read_fakequakes_hypo_time(home,project_name,rupture_name)
        # Put in matrix
        m,G=get_fakequakes_G_and_m(Nss,Ess,Zss,Nds,Eds,Zds,home,project_name,rupture_name,time_epi,GF_list,epicenter,NFFT,source_time_function,stf_falloff_rate)
        # Solve
        waveforms=G.dot(m)
        #Write output
        write_fakequakes_waveforms(home,project_name,rupture_name,waveforms,GF_list,NFFT,time_epi,dt)
        
        
        
            

def load_fakequakes_synthetics(home,project_name,fault_name,model_name,GF_list,G_from_file,G_name):
    ''''
    Load the miniseed files with all the synthetics
    '''
    from numpy import genfromtxt,loadtxt
    from obspy import read    
    from string import rjust

    vord='disp'
    if G_from_file==True: #load from file
        Eds=read(home+project_name+'/GFs/matrices/'+G_name+'.Eds.'+vord+'.mseed')
        Nds=read(home+project_name+'/GFs/matrices/'+G_name+'.Nds.'+vord+'.mseed')
        Zds=read(home+project_name+'/GFs/matrices/'+G_name+'.Zds.'+vord+'.mseed')
        Ess=read(home+project_name+'/GFs/matrices/'+G_name+'.Ess.'+vord+'.mseed')
        Nss=read(home+project_name+'/GFs/matrices/'+G_name+'.Nss.'+vord+'.mseed')
        Zss=read(home+project_name+'/GFs/matrices/'+G_name+'.Zss.'+vord+'.mseed')
    else: #assemble G one data type at a time, just displacememnt right now
        #Load station info
        station_file=home+project_name+'/data/station_info/'+GF_list
        staname=genfromtxt(station_file,dtype="S6",usecols=0)
        Nsta=len(staname)
        #Load fault model
        source=loadtxt(home+project_name+'/data/model_info/'+fault_name,ndmin=2)
        Nfaults=source.shape[0] #Number of subfaults
        kindex=0
        for ksta in range(Nsta):
            print 'Reading green functions for station #'+str(ksta+1)+' of '+str(Nsta)
            for kfault in range(Nfaults):
                #Get subfault GF directory
                nsub='sub'+rjust(str(int(source[kfault,0])),4,'0')
                nfault='subfault'+rjust(str(int(source[kfault,0])),4,'0')
                strdepth='%.4f' % source[kfault,3]
                syn_path=home+project_name+'/GFs/dynamic/'+model_name+'_'+strdepth+'.'+nsub+'/'
                #Get synthetics
                if kfault==0 and ksta==0: #It's the first one, initalize stream object
                    Ess=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.e')
                    Nss=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.n')
                    Zss=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.z')
                    Eds=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.e')
                    Nds=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.n')
                    Zds=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.z')
                else: #Just add to stream object
                    Ess+=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.e')
                    Nss+=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.n')
                    Zss+=read(syn_path+staname[ksta]+'.'+nfault+'.SS.'+vord+'.z')
                    Eds+=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.e')
                    Nds+=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.n')
                    Zds+=read(syn_path+staname[ksta]+'.'+nfault+'.DS.'+vord+'.z')
                kindex+=1
        print 'Writting synthetics to miniSEED, hang on this might take a minute or two.'
        Ess.write(home+project_name+'/GFs/matrices/'+G_name+'.Ess.'+vord+'.mseed',format='MSEED')
        Nss.write(home+project_name+'/GFs/matrices/'+G_name+'.Nss.'+vord+'.mseed',format='MSEED')
        Zss.write(home+project_name+'/GFs/matrices/'+G_name+'.Zss.'+vord+'.mseed',format='MSEED')
        Eds.write(home+project_name+'/GFs/matrices/'+G_name+'.Eds.'+vord+'.mseed',format='MSEED')
        Nds.write(home+project_name+'/GFs/matrices/'+G_name+'.Nds.'+vord+'.mseed',format='MSEED')
        Zds.write(home+project_name+'/GFs/matrices/'+G_name+'.Zds.'+vord+'.mseed',format='MSEED')
    return Nss,Ess,Zss,Nds,Eds,Zds



def get_fakequakes_G_and_m(Nss,Ess,Zss,Nds,Eds,Zds,home,project_name,rupture_name,time_epi,GF_list,epicenter,NFFT,source_time_function,stf_falloff_rate):
    '''
    Assemble Green functions matrix. If requested will parse all available synthetics on file and build the matrix.
    Otherwise, if it exists, it will be loaded from file 
    
    IN:
        home: Home directory location
        project_name: Name of the problem
        fault_name: Name of fault description file
        model_name: Name of velocity structure file
        GF_list: Name of GF control file
        G_from_file: if =0 build G from synthetics on file. If =1 then load from file
        G_name: If building G fromsynthetics then this is the name G will be saved with
            in binary .npy format. If loading from file this is the name to be looked for. 
            It is not necessary to supply the .npy extension
        epicenter: Epicenter coordinates
        rupture_speed: Fastest rupture speed allowed in the problem
        num_windows: Number of temporal rupture windows allowed
        decimate: Constant decimationf actor applied to GFs, set =0 for no decimation
        
    OUT:
        G: Fully assembled GF matrix
    '''
    
    from numpy import genfromtxt,loadtxt,convolve,where,zeros,arange,unique

    source=loadtxt(home+project_name+'/output/ruptures/'+rupture_name,ndmin=2)
    rise_times=source[:,7]
    rupture_onset=source[:,12]
    
    #How many unique faults?
    Nfaults=len(unique(source[:,0]))
    
    #How many subfaults are non-zero?
    i_non_zero=where(rise_times>0)[0]
    N_non_zero=len(i_non_zero)
    
    #Stations
    station_file=home+project_name+'/data/station_info/'+GF_list
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    Nsta=len(staname)
    
    #Initalize G matrix
    G=zeros((NFFT*3*Nsta,N_non_zero*2))
    
    #Place synthetics in correct place in Gmatrix
    matrix_pos=0 #tracks where in matrix synths are placed
    read_start=0  #Which trace to start reading from
    for ksta in range(Nsta):
        for ksource in range(len(i_non_zero)):
            #Get synthetics
            nss=Nss[read_start+i_non_zero[ksource]].copy()
            ess=Ess[read_start+i_non_zero[ksource]].copy()
            zss=Zss[read_start+i_non_zero[ksource]].copy()
            nds=Nds[read_start+i_non_zero[ksource]].copy()
            eds=Eds[read_start+i_non_zero[ksource]].copy()
            zds=Zds[read_start+i_non_zero[ksource]].copy()
            #Delay synthetics by rupture onset
            tdelay=rupture_onset[i_non_zero[ksource]]
            nss,ess,zss,nds,eds,zds=tshift_trace(nss,ess,zss,nds,eds,zds,tdelay,time_epi,NFFT)
            #Convolve with source time function
            rise=rise_times[i_non_zero[ksource]]
            #Make sure rise time is a multiple of dt
            dt=nss.stats.delta
            rise=round(rise/dt)*nss.stats.delta
            if rise<(2.*dt): #Otherwise get nan's in STF
                rise=2.*dt
            total_time=NFFT*dt
            t_stf,stf=build_source_time_function(rise,dt,total_time,stf_type=source_time_function,dreger_falloff_rate=stf_falloff_rate)
            nss.data=convolve(nss.data,stf)[0:NFFT]
            ess.data=convolve(ess.data,stf)[0:NFFT]
            zss.data=convolve(zss.data,stf)[0:NFFT]
            nds.data=convolve(nds.data,stf)[0:NFFT]
            eds.data=convolve(eds.data,stf)[0:NFFT]
            zds.data=convolve(zds.data,stf)[0:NFFT]
            #Place in matrix
            G[matrix_pos:matrix_pos+NFFT,2*ksource]=nss.data
            G[matrix_pos:matrix_pos+NFFT,2*ksource+1]=nds.data
            G[matrix_pos+NFFT:matrix_pos+2*NFFT,2*ksource]=ess.data
            G[matrix_pos+NFFT:matrix_pos+2*NFFT,2*ksource+1]=eds.data
            G[matrix_pos+2*NFFT:matrix_pos+3*NFFT,2*ksource]=zss.data
            G[matrix_pos+2*NFFT:matrix_pos+3*NFFT,2*ksource+1]=zds.data
        matrix_pos+=3*NFFT
        read_start+=Nfaults
        #Get slip model vector
    m=zeros((N_non_zero*2,1))
    iss=arange(0,len(m),2)
    ids=arange(1,len(m),2)
    m[iss,0]=source[i_non_zero,8]
    m[ids,0]=source[i_non_zero,9]

    return m,G


def write_fakequakes_waveforms(home,project_name,rupture_name,waveforms,GF_list,NFFT,time_epi,dt):
    '''
    write output from fakequakes run
    '''
    
    from os import path,makedirs
    from numpy import genfromtxt,squeeze,sqrt
    from obspy import Stream,Trace
    
    #Where am I writting to?
    rupture=rupture_name.split('.')[0]+'.'+rupture_name.split('.')[1]
    directory=home+project_name+'/output/waveforms/'+rupture+'/'
    
    #Check if dir exists if not then create it
    if not path.exists(directory):
        makedirs(directory)
    
    # Get station list and coords
    sta=genfromtxt(home+project_name+'/data/station_info/'+GF_list,usecols=0,dtype='S') 
    lon=genfromtxt(home+project_name+'/data/station_info/'+GF_list,usecols=1)  
    lat=genfromtxt(home+project_name+'/data/station_info/'+GF_list,usecols=2)  
    line_out='# Station, lon, lat, N[m], E[m], Up[m], PGD[m]\n'
    #Parse waveforms vector
    read_pos=0
    for ksta in range(len(sta)):
        # Init waveforms and metadata
        n=Stream(Trace())
        n[0].stats.starttime=time_epi
        n[0].stats.delta=dt
        # Copy to the other components
        e=n.copy()
        z=n.copy()
        # Get the actual data
        n[0].data=squeeze(waveforms[read_pos:read_pos+NFFT])
        e[0].data=squeeze(waveforms[read_pos+NFFT:read_pos+2*NFFT])
        z[0].data=squeeze(waveforms[read_pos+2*NFFT:read_pos+3*NFFT])
        # Extract coseismic offsets
        n_offset=n[0].data[-10:].mean()
        e_offset=e[0].data[-10:].mean()
        z_offset=z[0].data[-10:].mean()
        # Get PGD
        pgd=sqrt(n[0].data**2+e[0].data**2+z[0].data**2).max()
        # Summary file
        line_out+='%s\t%10.4f\t%10.4f\t%10.6f\t%10.6f\t%10.6f\t%10.6f\n' % (sta[ksta],lon[ksta],lat[ksta],n_offset,e_offset,z_offset,pgd)
        # write to file
        n.write(directory+sta[ksta]+'.LYN.sac',format='SAC')
        e.write(directory+sta[ksta]+'.LYE.sac',format='SAC')
        z.write(directory+sta[ksta]+'.LYZ.sac',format='SAC')
        # update counter
        read_pos+=3*NFFT
    f=open(directory+'_summary.'+rupture+'.txt','w')
    f.write(line_out)
    f.close()
        
        
       


def coseismics(home,project_name,rupture_name,station_file,hot_start=None):
    '''
    This routine will take synthetics and apply a static slip dsitibution. It will 
    linearly superimpose the synthetic coseismic from each subfault. Output will be
    a single ascii file witht he 3 coseismic offsets (NEU) for each station defined 
    in the station_file. Depending on the specified rake angle at each subfault the 
    code will compute the contribution to dip and strike slip directions. It will 
    also compute the moment at that subfault and scale it according to the unit 
    amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,array,savetxt,unique,where
    from string import rjust
    
    print 'Solving for static problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    #load source
    source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    station_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #Get unique sources
    source_id=unique(source[:,0])
    #Loop over stations
    if hot_start is None:
        hot_start=0
    for ksta in range(hot_start,len(staname)):
        #Initalize output
        n=array([0])
        e=array([0])
        z=array([0])
        sta=staname[ksta]
        print 'Working on station '+staname[ksta]+' ('+str(ksta+1)+'/'+str(len(staname))+')'
        #Loop over sources
        for k in range(len(source_id)):
            print k
            #Get subfault parameters
            nfault='subfault'+rjust(str(int(source_id[k])),4,'0')
            ifault=where(source[:,0]==source_id[k])[0]
            ss_slip=source[ifault,8].sum()
            ds_slip=source[ifault,9].sum()
            print 'ds_slip='+str(ds_slip)
            #Where's the data
            syn_path=home+project_name+'/GFs/static/'
            #Get synthetics
            try:
                coseis_ss=loadtxt(syn_path+sta+'.'+nfault+'.SS.static.neu')
            except:
                coseis_ss=array([0,0,0])
            nss=coseis_ss[0]
            ess=coseis_ss[1]
            zss=coseis_ss[2]
            try:
                coseis_ds=loadtxt(syn_path+sta+'.'+nfault+'.DS.static.neu')
            except:
                coseis_ds=array([0,0,0])
            nds=coseis_ds[0]
            eds=coseis_ds[1]
            zds=coseis_ds[2]
            print 'zds='+str(zds)
            #get rake contribution and moment multiplier
            etotal=ds_slip*eds+ss_slip*ess
            ntotal=ds_slip*nds+ss_slip*nss
            ztotal=ds_slip*zds+ss_slip*zss
            print 'ztotal='+str(ztotal)
            #Add to previous subfault's results
            e=e+etotal
            n=n+ntotal
            z=z+ztotal
            print 'n='+str(n)
            print 'e='+str(e)
            print 'z='+str(z)
        #Save results
        savetxt(outpath+sta+'.static.neu',(n,e,z))


def coseismics_matrix(home,project_name,rupture_name,station_file,G_from_file,G_name):
    '''
    This routine will take synthetics and apply a static slip dsitibution. It will 
    linearly superimpose the synthetic coseismic from each subfault. Output will be
    a single ascii file witht he 3 coseismic offsets (NEU) for each station defined 
    in the station_file. Depending on the specified rake angle at each subfault the 
    code will compute the contribution to dip and strike slip directions. It will 
    also compute the moment at that subfault and scale it according to the unit 
    amount of momeent (1e15 N-m)
    
    IN:
        home: Home directory
        project_name: Name of the problem
        rupture_name: Name of rupture description file
        station_file: File with coordinates of stations
        model_Name: Name of Earth structure model file
       
    OUT:
        Nothing
    '''
    from numpy import loadtxt,genfromtxt,array,savetxt,unique,where,zeros,load,save
    from string import rjust
    
    print 'Solving for static problem'
    #Output where?
    outpath=home+project_name+'/output/forward_models/'
    #load source
    source=loadtxt(home+project_name+'/forward_models/'+rupture_name,ndmin=2)
    #Load stations
    station_file=home+project_name+'/data/station_info/'+station_file
    staname=genfromtxt(station_file,dtype="S6",usecols=0)
    #Get unique sources
    source_id=unique(source[:,0])
    m=zeros((2*len(source_id),1))
    #Assemble source parameters vector
    for ksta in range(len(staname)):
        for ksource in range(len(source_id)):
            #Get subfault parameters
            nfault='subfault'+rjust(str(int(source_id[ksource])),4,'0')
            ifault=where(source[:,0]==source_id[ksource])[0]
            #Combine into model vector
            ss_slip=source[ifault,8].sum()
            ds_slip=source[ifault,9].sum()
            m[2*ksource]=ss_slip
            m[2*ksource+1]=ds_slip
    
    
    #Do I need to make G or can I load it from file??
    G_name=home+project_name+'/GFs/matrices/'+G_name
    if G_from_file==True: #load from file
        if G_name[-3:]!='npy':
            G_name=G_name+'.npy'
        print 'Loading G from file '+G_name
        G=load(G_name)
    else:
    #initalize matrices
        G=zeros((3*len(staname),2*len(source_id)))
        print '... Assembling GFs matrix'
        #Loop over stations
        for ksta in range(len(staname)):
            if ksta % 10 == 0:
                print '... ... Loading station %i of %i' %(ksta,len(staname))
            sta=staname[ksta]
            #Loop over sources
            for ksource in range(len(source_id)):
                #Get subfault parameters
                nfault='subfault'+rjust(str(int(source_id[ksource])),4,'0')
                #Where's the synthetic data
                syn_path=home+project_name+'/GFs/static/'
                #Get synthetics
                try:
                    coseis_ss=loadtxt(syn_path+sta+'.'+nfault+'.SS.static.neu')
                except:
                    coseis_ss=array([0,0,0])
                nss=coseis_ss[0]
                ess=coseis_ss[1]
                zss=coseis_ss[2]
                try:
                    coseis_ds=loadtxt(syn_path+sta+'.'+nfault+'.DS.static.neu')
                except:
                    coseis_ds=array([0,0,0])
                nds=coseis_ds[0]
                eds=coseis_ds[1]
                zds=coseis_ds[2]
                #Put in matrix
                #North
                G[3*ksta,2*ksource]=nss  ;  G[3*ksta,2*ksource+1]=nds
                #East
                G[3*ksta+1,2*ksource]=ess  ;  G[3*ksta+1,2*ksource+1]=eds
                #East
                G[3*ksta+2,2*ksource]=zss  ;  G[3*ksta+2,2*ksource+1]=zds
        #Save G matrix
        print 'Saving GF matrix to '+G_name+' this might take just a second...'
        save(G_name,G)
    #Now go on to matrix multiply and save solutions
    print 'Matrix multiplying and saving output...DONE'
    d=G.dot(m)
    for ksta in range(len(staname)):
        sta=staname[ksta]
        n=d[3*ksta]
        e=d[3*ksta+1]
        z=d[3*ksta+2]
        savetxt(outpath+sta+'.static.neu',(n,e,z))
    





def tsunami_waveforms(home,project_name,fault_name,rupture_name,station_file,model_name,run_name,GF_list,G_from_file,G_name,epicenter,
                rupture_speed,num_windows,coord_type,decimate,lowpass,resample,beta):            
    '''
    Forward compute tsunami waveforms the right way, load the GF matrix and just multiply by fault model
    '''
    from mudpy.inverse import getG
    from numpy import genfromtxt,zeros,arange,deg2rad,cos,sin,vstack,array,where
    from obspy import read

    #Read GFs
    G=getG(home,project_name,fault_name,model_name,GF_list,G_from_file,G_name,epicenter,
                rupture_speed,num_windows,coord_type,decimate,lowpass)
    #Read rupture model and convert into vector
    ss=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=8)
    ds=genfromtxt(home+project_name+'/forward_models/'+rupture_name,usecols=9)
    #Rotate by beta
    if beta != None:
        beta_rot=deg2rad(beta)
        R=array([[cos(beta_rot),sin(beta_rot)],[-sin(beta_rot),cos(beta_rot)]])
        rot=R.dot(vstack((ss,ds)))
        ss_rot=rot[0,:]
        ds_rot=rot[1,:]
    #Assemble into column vector
    m=zeros(len(ss)*2)
    iss=arange(0,len(m),2)
    ids=arange(1,len(m),2)
    m[iss]=ss_rot
    m[ids]=ds_rot
    #Multiply
    dtsun=G.dot(m)
    #Write to file (Modified from inverse.write_synthetics)
    #Read gf file and decide what needs to get loaded
    gf_file=home+project_name+'/data/station_info/'+GF_list
    stations=genfromtxt(gf_file,usecols=[0],skip_header=1,dtype='S')
    GF=genfromtxt(gf_file,usecols=[3,4,5,6,7],skip_header=1,dtype='f8')
    GFfiles=genfromtxt(gf_file,usecols=[8,9,10,11,12],skip_header=1,dtype='S')
    #Separate into its constituent parts (statics,displacaments, velocities, etc...)
    kinsert=0
    kgf=3
    i=where(GF[:,kgf]==1)[0]
    if len(i)>0:
        for ksta in range(len(i)):
            sta=stations[i[ksta]]
            tsun=read(GFfiles[i[ksta],kgf])
            npts=tsun[0].stats.npts
            synth=tsun.copy()
            synth[0].data=dtsun[kinsert:kinsert+npts]
            kinsert+=npts
            synth.write(home+project_name+'/output/forward_models/'+run_name+'.'+sta+'.tsun',format='SAC')

            
                        
                                 
                                                            
                        
                                                
def move_seafloor(home,project_name,run_name,topo_dx_file,topo_dy_file,tgf_file,
        outname,time_epi,tsun_dt,maxt,coast_file,topo_effect=True,variance=None,static=False):
    '''
    Create moving topography input files for geoclaw
    '''
    import datetime
    from numpy import genfromtxt,zeros,meshgrid,ones,c_,savetxt,delete,where,nan,argmin,arange
    from obspy import read
    from string import rjust
    from netCDF4 import Dataset
    from scipy.interpolate import griddata
    from mudpy.inverse import interp_and_resample,grd2xyz
    from scipy.ndimage.filters import gaussian_filter


    #Get station names
    sta=genfromtxt(home+project_name+'/data/station_info/'+tgf_file)
    stanames=genfromtxt(home+project_name+'/data/station_info/'+tgf_file,usecols=0,dtype='S')
    #lon=360+sta[:,1]
    lon=sta[:,1]
    print 'correcting longitude'
    print lon[0]
    lat=sta[:,2]
    #Get fault file
    #f=genfromtxt(home+project_name+'/data/model_info/'+fault_name)
    #Where is the data
    data_dir=home+project_name+'/output/forward_models/'
    #Define time deltas
    td_max=datetime.timedelta(seconds=maxt)
    #Maximum tiem to be modeled
    tmax=time_epi+td_max
    #Read derivatives
    bathy_dx=Dataset(topo_dx_file,'r',format='NETCDF4')
    zdx=bathy_dx.variables['z'][:].data
    bathy_dy=Dataset(topo_dy_file,'r',format='NETCDF4')
    zdy=bathy_dy.variables['z'][:].data
    #Make interpolation quantities
    try:
        loni=bathy_dx.variables['x'][:]
        lati=bathy_dx.variables['y'][:]
    except:
        loni=bathy_dx.variables['lon'][:]
        lati=bathy_dx.variables['lat'][:]
    loni,lati=meshgrid(loni,lati)
    #Read slope file
    kwrite=0
    idelete=[]
    for ksta in range(len(sta)):
        if ksta%500==0:
            print '... ... working on seafloor grid point '+str(ksta)+' of '+str(len(sta))
        try: #If no data then delete
            if static==False: #We're reading waveforms
                #e=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.e')
                #n=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.n')
                #u=read(data_dir+run_name+'.'+rjust(str(int(sta[ksta,0])),4,'0')+'.disp.z')
                #e=read(data_dir+run_name+'.'+stanames[ksta]+'.disp.e')
                #n=read(data_dir+run_name+'.'+stanames[ksta]+'.disp.n')
                #u=read(data_dir+run_name+'.'+stanames[ksta]+'.disp.u')
                e=read(data_dir+stanames[ksta]+'.disp.e')
                n=read(data_dir+stanames[ksta]+'.disp.n')
                u=read(data_dir+stanames[ksta]+'.disp.u')
                e=interp_and_resample(e,1.0,time_epi)
                n=interp_and_resample(n,1.0,time_epi)
                u=interp_and_resample(u,1.0,time_epi)
                #Keep only data between time_epi and tmax
                e.trim(time_epi,tmax,fill_value=e[0].data[-1],pad=True)
                n.trim(time_epi,tmax,fill_value=n[0].data[-1],pad=True)
                u.trim(time_epi,tmax,fill_value=u[0].data[-1],pad=True)
                #Initalize matrices
                if ksta==0:
                    emat=zeros((n[0].stats.npts,len(sta)))
                    nmat=emat.copy()
                    umat=emat.copy()
                #Populate matrix
                emat[:,kwrite]=e[0].data
                nmat[:,kwrite]=n[0].data
                umat[:,kwrite]=u[0].data
            else:
                neu=genfromtxt(data_dir+stanames[ksta]+'.static.neu')
                n=neu[0]
                e=neu[1]
                u=neu[2]
                tsun_dt=1.0
                maxt=1.0
                if ksta==0:
                    emat=zeros((1,len(sta)))
                    nmat=emat.copy()
                    umat=emat.copy()
                #Populate matrix
                emat[:,kwrite]=e
                nmat[:,kwrite]=n
                umat[:,kwrite]=u
            kwrite+=1
        except: #Data was missing, delete from lat,lon
            pass
            print 'No data for station '+str(ksta)+', deleting from coordinates list'
            idelete.append(ksta)
    #Clean up missing data
    if len(idelete)!=0:
        lat=delete(lat,idelete)
        lon=delete(lon,idelete)
        emat=emat[:,:-len(idelete)]
        nmat=nmat[:,:-len(idelete)]
        umat=umat[:,:-len(idelete)]
    
    #Now go one epoch at a time, and interpolate all fields
    #Only apply topo effect to some points
    if coast_file!=None:
        #Straight line coordinates
        coast=genfromtxt(coast_file)
        #Get mask for applying horizontal effect
        mask=zeros(loni.shape)
        for k1 in range(loni.shape[0]):
            for k2 in range(loni.shape[1]):
                ip=argmin(abs(lati[k1,k2]-coast[:,1]))
                if loni[k1,k2]>coast[ip,0]:#Change this depending on which direction you want effect to be applied
                    print 'Applying coastal mask'
                    mask[k1,k2]=nan
        imask1,imask2=where(mask==0)#Points tot he right DO apply horiz. effect
    print '... interpolating coseismic offsets to a regular grid'
    nt_iter=umat.shape[0]
    for kt in range(nt_iter):
        if kt%20==0:
            print '... ... working on time slice '+str(kt)+' of '+str(nt_iter)
        ninterp=griddata((lon,lat),nmat[kt,:],(loni,lati),method='cubic',fill_value=0)
        einterp=griddata((lon,lat),emat[kt,:],(loni,lati),method='cubic',fill_value=0)
        uinterp=griddata((lon,lat),umat[kt,:],(loni,lati),method='cubic',fill_value=0)
        #Output vertical
        uout=uinterp.copy()
        #Apply effect of topography advection
        if topo_effect==False:
            print 'WARNING: No topography effect added'
        else:
            print 'Applying topo effect'
            if coast_file==None: #Apply everywhere
                uout=uout+zdx*einterp+zdy*ninterp
            else: #Don't apply topo effect on dry land
                uout[imask1,imask2]=uout[imask1,imask2]+zdx[imask1,imask2]*einterp[imask1,imask2]+zdy[imask1,imask2]*ninterp[imask1,imask2]
        #print 'no horiz'
        #Filter?
        if variance!=None:
            uout=gaussian_filter(uout,variance)
        #Convert to column format and append
        xyz=grd2xyz(uout,loni,lati)
        tvec=(kt*tsun_dt)*ones((len(xyz),1))
        if kt==0: #Intialize
            numel=uout.size #Number of elements in grid
            kwrite=numel #Where to write the data
            dtopo=zeros((numel*nt_iter,4))
            dtopo[0:kwrite,1:3]=xyz[:,0:2]
        else:
            dtopo[kwrite:kwrite+numel,:]=c_[tvec,xyz]
            kwrite=kwrite+numel
        if static==True:
            tvec=ones(tvec.shape)
            numel=uout.size*2 #Number of elements in grid
            kwrite=numel/2 #Where to write the data
            dtopo=zeros((numel*nt_iter,4))
            dtopo[0:kwrite,1:3]=xyz[:,0:2]
            dtopo[kwrite:kwrite+numel,1:3]=xyz[:,0:2]
            dtopo[kwrite:kwrite+numel,:]=c_[tvec,xyz]
            kwrite=kwrite+numel
    print '... writting dtopo files'
    savetxt(data_dir+outname+'.dtopo',dtopo,fmt='%i\t%.6f\t%.6f\t%.4e')   
    print 'Output to '+data_dir+outname+'.dtopo' 
            

def move_seafloor_okada(mudpy_file,out_file,x,y,refine_factor=None,mu=40e9,return_object=False):
    """
    Use the Okada routine in GeoClaw to generate the dtopo file
    """
    
    from clawpack.geoclaw import dtopotools
    from numpy import genfromtxt,arctan2,rad2deg,squeeze
    from copy import deepcopy
    
    #load rupture info
    f=genfromtxt(mudpy_file)
    
    #init object
    fault = dtopotools.Fault() 
              
    #Make one subfault object at a time
    for k in range(0,len(f)):
        subfault = dtopotools.SubFault()
        subfault.strike = f[k,4]
        subfault.dip = f[k,5]
        #Vertical faults introduce errors
        if subfault.dip==90:
            subfault.dip=89.9
        subfault.rake = rad2deg(arctan2(f[k,9],f[k,8]))
        subfault.mu=mu
        subfault.coordinate_specification = "centroid"                
        subfault.length = f[k,10]
        subfault.width = f[k,11]
        subfault.depth = f[k,3]*1000
        subfault.slip = (f[k,9]**2+f[k,8]**2)**0.5
        subfault.longitude = f[k,1]
        subfault.latitude = f[k,2]
        if refine_factor!=None:
            #How many times are we doing it?
            for ksplit in range(int(refine_factor)):
                if ksplit==0:    
                    subfault_list=split_subfault(subfault)
                else:
                    subfault_list=split_subfault(subfault_list)#len(split_subfault(subfault_list)) len(subfault_list)
        #Decide how to append     
        if k==0:
            if refine_factor==None:
                fault.subfaults=[subfault]
            else:
                fault.subfaults=deepcopy(subfault_list)
        else:
            if refine_factor==None:
                fault.subfaults.append(subfault)
            else:
                fault.subfaults.extend(subfault_list)
     
    ##Run Okada   
    fault.create_dtopography(x,y,times=[0.,1.],verbose=True)
    
    #Get dtopo
    dtopo=fault.dtopo
    dtopo.write(path=out_file,dtopo_type=1)
    
    if return_object:
        return fault
    


def split_subfault(subfault_list):
    '''
    Split a subfault object into 4 samller subfaults
    '''
    
    from pyproj import Geod
    from numpy import deg2rad,cos,sin
    from copy import deepcopy
    
    try:
        Nsubs=len(subfault_list)
    except:
        Nsubs=1
    #Loop over all elements in subfault_list
    for ksub in range(Nsubs):
        if Nsubs==1:
            subfault=deepcopy(subfault_list)
        else:
            subfault=deepcopy(subfault_list[ksub])
            
    
        #Assing useful object properties
        lon=subfault.longitude
        lat=subfault.latitude
        depth=subfault.depth
        strike=subfault.strike
        dip=subfault.dip
        L=subfault.length
        W=subfault.width
        
        #Projection object
        P=Geod(ellps='WGS84')
        
        #Lon lat of pseudo centers
        lon_P1,lat_P1,baz=P.fwd(lon,lat,strike,L/4.0)
        lon_P2,lat_P2,baz=P.fwd(lon,lat,strike,-L/4.0)
        
        # Pseudo widths
        wH=W*cos(deg2rad(dip))
        wV=W*sin(deg2rad(dip))
        
        #Get final lon lat depth of 4 new faults
        lon1,lat1,baz=P.fwd(lon_P1,lat_P1,strike-90,wH/4.0)
        lon2,lat2,baz=P.fwd(lon_P1,lat_P1,strike-90,-wH/4.0)
        z1=depth-wV/4.
        z2=depth+wV/4.
        
        lon3,lat3,baz=P.fwd(lon_P2,lat_P2,strike-90,wH/4.0)
        lon4,lat4,baz=P.fwd(lon_P2,lat_P2,strike-90,-wH/4.0)
        z3=depth-wV/4.
        z4=depth+wV/4.
        
        #Assemble into subfault objects and into list
        subfault1 = deepcopy(subfault)
        subfault2 = deepcopy(subfault)
        subfault3 = deepcopy(subfault)
        subfault4 = deepcopy(subfault)
        
        subfault1.length = subfault2.length = subfault3.length = subfault4.length = L/2.
        subfault1.width = subfault2.width = subfault3.width = subfault4.width = W/2.
        
        subfault1.longitude=lon1 ; subfault1.latitude=lat1 ; subfault1.depth=z1
        subfault2.longitude=lon2 ; subfault2.latitude=lat2 ; subfault2.depth=z2
        subfault3.longitude=lon3 ; subfault3.latitude=lat3 ; subfault3.depth=z3
        subfault4.longitude=lon4 ; subfault4.latitude=lat4 ; subfault4.depth=z4
        
        if ksub==0:
            subfault_list_out=[subfault1,subfault2,subfault3,subfault4]
        else:
            subfault_list_out.extend([subfault1,subfault2,subfault3,subfault4])
            
    return subfault_list_out




###########                Tools and trinkets                      #############
    
def get_mu(structure,zs):
    '''
    Look in structure model and compute rigidity given a source depth
    
    IN:
        structure: Array with velocity structure information
        zs: depth in km at which you want to compute mu
        
    OUT:
        mu: Rigidity in Pa
    '''
    from numpy import nonzero
    
    if len(structure)>1: #Model is more than jsut the halfspace
        Z=structure[:,0].cumsum()
        #Which layer do I want?
        i=nonzero(zs>Z)[0]
        if i.size==0: #It's in top layer
            imu=0
        else:
            imu=max(i)+1
        if imu>=structure.shape[0]:
            imu=imu-1#It's int he half-space
        mu=((1000*structure[imu,1])**2)*structure[imu,3]*1000
        #print "Rigidity at z="+str(zs)+' is, mu = '+str(mu/1e9)+'GPa'
    else: #Model is a halfspace
        mu=((1000*structure[0,1])**2)*structure[0,3]*1000
    return mu

def get_source_time_function(mu,area,rise_time,t0,slip):
    '''
    Compute source time function for a given rise time, right now it assumes 1m of slip
    and a triangle STF
    '''
    from numpy import zeros,linspace,where
    
    rise_time=float(rise_time)
    #Initialize outputs
    t=linspace(t0,t0+rise_time,1000)
    Mdot=zeros(t.shape)
    #Triangle gradient
    m=4*mu*area/(rise_time**2)
    #Upwards intercept
    b1=-m*t0
    #Downwards intercept
    b2=m*(t0+rise_time)
    #Assign moment rate
    i=where(t<=t0+rise_time/2)[0]
    Mdot[i]=m*t[i]+b1
    i=where(t>t0+rise_time/2)[0]
    Mdot[i]=-m*t[i]+b2 
    Mdot=Mdot*slip  
    return t,Mdot
    
def add2stf(t1,Mdot1,t2,Mdot2):
    '''
    Add two overlapping source time functions
    '''
    from numpy import interp,linspace
    #Make interpolation vector
    tstart=min(t1[0],t2[0])
    tend=max(t1[-1],t2[-1])
    ti=linspace(tstart,tend,10000)
    #Interpolate
    Mdot1_interp=interp(ti,t1,Mdot1,left=0,right=0)
    Mdot2_interp=interp(ti,t2,Mdot2,left=0,right=0)
    #Add them up
    Mdot_out=Mdot1_interp+Mdot2_interp
    return ti,Mdot_out
    

def add_traces(ss,ds,ssmult,dsmult):
    '''
    Add two stream objects with dip slip and strike slip contributions. This code will take
    two stream objects and super impsoe them according tot he weights defined by ssmult
    dsmult. If one waveform is longer than the other then the code will extend the
    shorter waveform by padding it with the last value.

    For simple addition use ss=ds=M=1
    
    IN:
        ss: Strike slip waveform
        ds: Dip-slip waveform
        ssmult: Strike-slip contribution (meters)
        dsmult: Strike-slip contribution (meters)
    
    OUT:
        st: Stream object with result of superposition
    '''
    from numpy import zeros
    
    #If one stream object is empty set it to zeros, if both are empty then freak out
    if ss.count()==0 and ds.count()==0:
        print 'FATAL ERROR: can\'t add 2 empty stream objects doofus'
        return None
    if ss.count()==0:
        ss=ds.copy()
        ss[0].data=zeros(ds[0].data.shape)
    elif ds.count()==0:
        ds=ss.copy()
        ds[0].data=zeros(ss[0].data.shape) 
        
    #Round times to dt sampling interval
    ss[0].stats.starttime=round_time(ss[0].stats.starttime,ss[0].stats.delta)
    ds[0].stats.starttime=round_time(ds[0].stats.starttime,ds[0].stats.delta)
    #Find earliest starttime
    if ss[0].stats.starttime<=ds[0].stats.starttime:
        t1=ss[0].stats.starttime
    else:
        t1=ds[0].stats.starttime
    #Find altest end time
    if ss[0].stats.endtime>=ds[0].stats.endtime:
        t2=ss[0].stats.endtime
    else:
        t2=ds[0].stats.endtime
    #Now extend both arrays and fill start with zeros then end with last sample
    ss[0].trim(t1,ss[0].stats.endtime,pad=True,fill_value=0)
    ds[0].trim(t1,ds[0].stats.endtime,pad=True,fill_value=0)
    fillend=ss[0].data[-60:-1].mean()
    ss[0].trim(t1,t2,pad=True,fill_value=fillend)
    fillend=ds[0].data[-20:-1].mean()
    ds[0].trim(t1,t2,pad=True,fill_value=fillend)
    #Apply rake scaling value
    ss[0].data=ss[0].data*ssmult
    ds[0].data=ds[0].data*dsmult
    #Creat output stream
    st=ss.copy()
    #Add and apply scale
    st[0].data=ss[0].data+ds[0].data
    #And done
    return st


def tshift(st,tshift):
    '''
    Shift a stream object by tshift seconds, positive moves forward in time
    
    IN:
        st: Stream object
        tshift: Number fo seconds to shift
    OUT:
        st: Shifted stream object
    '''
    from datetime import timedelta
    td=timedelta(seconds=tshift)
    st[0].stats.starttime=st[0].stats.starttime+td
    return st       
    
                        
def tshift_trace(nss,ess,zss,nds,eds,zds,tshift,time_epi,npts):
    '''
    Shift a stream object by tshift seconds, positive moves forward in time and then trim it
    so that it spans from time_epi to time_epi+(npts*dt).
    
    IN:
        st: Stream object
        tshift: Number fo seconds to shift
    OUT:
        st: Shifted stream object
    '''
    
    from datetime import timedelta
    from numpy import r_,zeros,ones
    
    # Shifted onset time
    tstart=nss.stats.starttime+timedelta(seconds=tshift)
    #How many positions from start of tr to start of trace?
    dt=nss.stats.delta
    nshift=int(round((tstart-time_epi)/dt))
    if nshift>0:
        #Place in output variable
        nss.data=r_[zeros(nshift),nss.data[0:npts-nshift]]
        ess.data=r_[zeros(nshift),ess.data[0:npts-nshift]]
        zss.data=r_[zeros(nshift),zss.data[0:npts-nshift]]
        nds.data=r_[zeros(nshift),nds.data[0:npts-nshift]]
        eds.data=r_[zeros(nshift),eds.data[0:npts-nshift]]
        zds.data=r_[zeros(nshift),zds.data[0:npts-nshift]]    
    else:
        nss.data=r_[nss.data[-nshift:],nss.data[-1]*ones(-nshift)]
        ess.data=r_[ess.data[-nshift:],ess.data[-1]*ones(-nshift)]
        zss.data=r_[zss.data[-nshift:],zss.data[-1]*ones(-nshift)]
        nds.data=r_[nds.data[-nshift:],nds.data[-1]*ones(-nshift)]
        eds.data=r_[eds.data[-nshift:],eds.data[-1]*ones(-nshift)]
        zds.data=r_[zds.data[-nshift:],zds.data[-1]*ones(-nshift)]
    
    return nss,ess,zss,nds,eds,zds
    
    
    
    
    
    ##Trim
    #dt=tr.stats.delta
    ##Round down start time
    #dt=dt*1e6 #Converts to microseconds
    #t1=tr.stats.starttime
    #t1.microsecond=int((t1.microsecond/int(dt))*dt)
    #tr.stats.starttime=t1
    
    
    ##Cut first to time_epi
    #tr.trim(starttime=time_epi,pad=True,fill_value=0)
    ##Cut to npts*dt
    #coseismic_offset=tr[-10:].mean()
    #tr.trim(endtime=time_epi+npts*dt,pad=True,fill_value=coseismic_offset)
    ##Round down start time
    #dt=dt*1e6 #Converts to microseconds
    #t1=tr.stats.starttime
    #t1.microsecond=int((t1.microsecond/int(dt))*dt)
    #tr.stats.starttime=t1
    ##Check the length
    #if tr.stats.npts>npts:
    #    extra_samples=tr.stats.npts-npts
    #    tr.data=tr.data[0:-extra_samples]
    #elif tr.stats.npts<npts:
    #    print 'ERROR in forward.tshift_trace, synthetic has fewer samples than required'
    #return tr                                                               
        
def round_time(t1,delta):
    '''
    Round the initial time of a waveform to the nearest multiple of the sampling rate
    IN:
        t1: UTC time object containing start time of waveform
        delta: Sampling interval of waveform in seconds
    OUT:
        t1: Rounded UTC time object
    '''
    from datetime import timedelta
    #Move start and end times to start exactly on the dt intervals
    dtmicro=delta*1e6
    intervals=t1.microsecond/dtmicro #How many intervals in microseconds
    adjustment=(round(intervals)-intervals)*dtmicro
    td=timedelta(microseconds=adjustment)
    t1=t1+td
    return t1

def upsample(st,delta):
    '''
    Go from a low sampling rate to a high sampling rate
    
    IN:
        st - stream object
        delta - sampling rate requested in seconds
    
    OUT:
        st - modified stream object
    '''
    
    from scipy.interpolate import interp1d
    from numpy import arange
    
    t=st[0].times()
    y=st[0].data
    #Make interpolant
    f=interp1d(t,y)
    ti=arange(t[0],t[-1],delta)
    #Interpoalte and reassign tos tream object
    yi=f(ti)
    st[0].data=yi
    st[0].stats.delta=delta

def lowpass(data,fcorner,fsample,order):
    '''
    Make a lowpass zero phase filter
    '''
    from scipy.signal import butter,filtfilt
    from numpy import size,array
    
    if size(fcorner)==2:
        ftype='bandpass'
    else:
        ftype='lowpass'
    fnyquist=fsample/2
    b, a = butter(order, array(fcorner)/(fnyquist),ftype)
    data_filt=filtfilt(b,a,data)
    return data_filt
    
def highpass(data,fcorner,fsample,order):
    '''
    Make a highpass zero phase filter
    '''
    from scipy.signal import butter,filtfilt
    from numpy import size,array
    
    fnyquist=fsample/2
    b, a = butter(order, array(fcorner)/(fnyquist),'highpass')
    data_filt=filtfilt(b,a,data)
    return data_filt
    

    
def inv2coulomb(rupt,epicenter,fout):
    '''
    Convert .inv file to Coulomb-ready .inp file
    
    IN:
        rupt - path ro rupture (.inv) file
    '''
    import pyproj
    from numpy import genfromtxt,unique,zeros,where,deg2rad,sin,cos
    
    #Read fault
    f=genfromtxt(rupt)
    #Get total slip by identifying unique fault numbers
    u=unique(f[:,0])
    ss=zeros(len(u))
    ds=zeros(len(u))
    all_ss=f[:,8]
    all_ds=f[:,9]
    for k in range(len(u)):
        i=where(u[k]==f[:,0])
        ss[k]=all_ss[i].sum()
        ds[k]=all_ds[i].sum()
    #Sum them
    slip=(ss**2+ds**2)**0.5
    #Get rake
    rake=ssds2rake(ss,ds)
    #Convert coordinate subfault centers to local cartesian
    g = pyproj.Geod(ellps='WGS84') # Use WGS84 ellipsoid.
    x=zeros(len(u))
    y=zeros(len(u))
    for k in range(len(u)):
        baz,az,d=pyproj.Geod.inv(g,f[k,1],f[k,2],epicenter[0],epicenter[1])
        x[k]=(d/1000)*sin(deg2rad(az))
        y[k]=(d/1000)*cos(deg2rad(az))
    #Get width and length to get coordiantes of top corners and strike,dip
    width=f[:,10]/1000
    length=f[:,11]/1000
    strike=f[:,4]
    dip=f[:,5]
    depth=f[:,3]
    top_mid_x=zeros(len(u))
    top_mid_y=zeros(len(u))
    top_direction=strike-90 #This is the angle that points towards the top edge of the fault
    xstart=zeros(len(u))
    ystart=zeros(len(u))
    xfin=zeros(len(u))
    yfin=zeros(len(u))
    ztop=zeros(len(u))
    zbot=zeros(len(u))
    for k in range(len(u)):
        top_mid_x[k]=x[k]+((width[k]/2)*cos(deg2rad(dip[k])))*sin(deg2rad(top_direction[k]))
        top_mid_y[k]=y[k]+((width[k]/2)*cos(deg2rad(dip[k])))*cos(deg2rad(top_direction[k]))
        xstart[k]=top_mid_x[k]+(width[k]/2)*sin(deg2rad(strike[k]-180))
        ystart[k]=top_mid_y[k]+(width[k]/2)*cos(deg2rad(strike[k]-180))
        xfin[k]=top_mid_x[k]+(width[k]/2)*sin(deg2rad(strike[k]))
        yfin[k]=top_mid_y[k]+(width[k]/2)*cos(deg2rad(strike[k]))
        ztop[k]=depth[k]-(length[k]/2)*sin(deg2rad(dip[k]))
        zbot[k]=depth[k]+(length[k]/2)*sin(deg2rad(dip[k]))
    #Write to file and then manually add the ehaders and footers by copy pasting from some NEIC file (LAZY!)
    f=open(fout,'w')
    for k in range(len(u)):
        #out='1   %10.4f %10.4f %10.4f %10.4f 100 %10.4f %10.4f %10.4f %10.4f %10.4f %i\n' % (xstart[k],ystart[k],xfin[k],yfin[k],rake[k],slip[k],dip[k],ztop[k],zbot[k],k)
        out='1   %10.4f %10.4f %10.4f %10.4f 100 %10.4f %10.4f %10.4f %10.4f %10.4f %i\n' % (xstart[k],ystart[k],xfin[k],yfin[k],-ss[k],ds[k],dip[k],ztop[k],zbot[k],k)
        f.write(out)
    f.close()
    
def coulomb_xy2latlon(f,epicenter,fout):
    '''
    Change the x-y coordinates of a Coulomb file to lat/lon
    '''
    from numpy import genfromtxt,zeros,rad2deg,arctan,isnan,savetxt
    import pyproj
    
    s=genfromtxt(f,delimiter=',')
    x=s[:,1]
    y=s[:,2]
    #Now use pyproj to dead reckon anf get lat/lon coordinates of subfaults
    g = pyproj.Geod(ellps='WGS84')
    #first get azimuths of all points, go by quadrant
    az=zeros(x.shape)
    for k in range(len(x)):
        if x[k]>0 and y[k]>0:
            az[k]=rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]>0:
            az[k]=360+rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
        if x[k]>0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
    #Quadrant correction
    #Now horizontal distances
    d=((x**2+y**2)**0.5)*1000
    #Now reckon
    lo=zeros(len(d))
    la=zeros(len(d))
    for k in range(len(d)):
        if isnan(az[k]): #No azimuth because I'm on the epicenter
            print 'Point on epicenter'
            lo[k]=epicenter[0]
            la[k]=epicenter[1]
        else:
            lo[k],la[k],ba=g.fwd(epicenter[0],epicenter[1],az[k],d[k])
    s[:,1]=lo
    s[:,2]=la
    savetxt(fout,s,fmt='%.6f')
    
def coulomb_disp_xy2latlon(f,epicenter,fout):
    '''
    Change the x-y coordinates of a Coulomb file to lat/lon
    '''
    from numpy import genfromtxt,zeros,rad2deg,arctan,isnan,savetxt,where
    import pyproj
    
    s=genfromtxt(f)
    x=s[:,0]
    y=s[:,1]
    #Fix problem with x=0 and y=0 lines
    i=where(x==0)[0]
    x[i]=0.001
    i=where(y==0)[0]
    y[i]=0.001
    #Now use pyproj to dead reckon anf get lat/lon coordinates of subfaults
    g = pyproj.Geod(ellps='WGS84')
    #first get azimuths of all points, go by quadrant
    az=zeros(x.shape)
    for k in range(len(x)):
        if x[k]>0 and y[k]>0:
            az[k]=rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]>0:
            az[k]=360+rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
        if x[k]>0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
    #Quadrant correction
    #Now horizontal distances
    d=((x**2+y**2)**0.5)*1000
    #Now reckon
    lo=zeros(len(d))
    la=zeros(len(d))
    for k in range(len(d)):
        if isnan(az[k]): #No azimuth because I'm on the epicenter
            print 'Point on epicenter'
            lo[k]=epicenter[0]
            la[k]=epicenter[1]
        else:
            lo[k],la[k],ba=g.fwd(epicenter[0],epicenter[1],az[k],d[k])
    s[:,0]=lo
    s[:,1]=la
    savetxt(fout,s,fmt='%.6f')
    
      
def ssds2rake(ss,ds):
    '''
    Compute rake angle in degrees
    '''
    from numpy import arctan,rad2deg,pi,zeros
    try:
        rake=zeros(len(ss))
    except:
        rake=zeros(1)
    for k in range(len(rake)):
        if ss[k]>0 and ds[k]>0:
            rake[k]=arctan(ds[k]/ss[k])
        elif ds[k]>0 and ss[k]<0:
            rake[k]=pi+arctan(ds[k]/ss[k])
        elif ds[k]<0 and ss[k]<0:
            rake[k]=pi+arctan(ds[k]/ss[k])
        elif ds[k]<0 and ss[k]>0:
            rake[k]=2*pi+arctan(ds[k]/ss[k])
    rake=rad2deg(rake)
    return rake
    
def makefault(fout,strike,dip,nstrike,dx_dip,dx_strike,epicenter,num_updip,num_downdip,rise_time):
    '''
    Make a planar fault
    
    strike - Strike angle (degs)
    dip - Dip angle (degs)200/5
    '''
    from numpy import arange,sin,cos,deg2rad,r_,ones,arctan,rad2deg,zeros,isnan,unique,where,argsort
    import pyproj
    
    proj_angle=180-strike #Angle to use for sin.cos projection (comes from strike)
    y=arange(-nstrike/2+1,nstrike/2+1)*dx_strike
    x=arange(-nstrike/2+1,nstrike/2+1)*dx_strike
    z=ones(x.shape)*epicenter[2]
    y=y*cos(deg2rad(strike))
    x=x*sin(deg2rad(strike))   
    #Save teh zero line
    y0=y.copy()
    x0=x.copy()
    z0=z.copy()
    #Initlaize temp for projection up/down dip
    xtemp=x0.copy()
    ytemp=y0.copy()
    ztemp=z0.copy()
    #Get delta h and delta z for up/ddx_dip=1own dip projection
    dh=dx_dip*cos(deg2rad(dip))
    dz=dx_dip*sin(deg2rad(dip))
    #Project updip lines
    for k in range(num_updip):
        xtemp=xtemp+dh*cos(deg2rad(proj_angle))
        ytemp=ytemp+dh*sin(deg2rad(proj_angle))
        ztemp=ztemp-dz
        x=r_[x,xtemp]
        y=r_[y,ytemp]
        z=r_[z,ztemp]
    #Now downdip lines
    xtemp=x0.copy()
    ytemp=y0.copy()
    ztemp=z0.copy()
    for k in range(num_downdip):
        xtemp=xtemp-dh*cos(deg2rad(proj_angle))
        ytemp=ytemp-dh*sin(deg2rad(proj_angle))
        ztemp=ztemp+dz
        x=r_[x,xtemp]
        y=r_[y,ytemp]
        z=r_[z,ztemp]
    #Now use pyproj to dead reckon anf get lat/lon coordinates of subfaults
    g = pyproj.Geod(ellps='WGS84')
    #first get azimuths of all points, go by quadrant
    az=zeros(x.shape)
    for k in range(len(x)):
        if x[k]>0 and y[k]>0:
            az[k]=rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]>0:
            az[k]=360+rad2deg(arctan(x[k]/y[k]))
        if x[k]<0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
        if x[k]>0 and y[k]<0:
            az[k]=180+rad2deg(arctan(x[k]/y[k]))
    #Quadrant correction
    #Now horizontal distances
    d=((x**2+y**2)**0.5)*1000
    #Now reckon
    lo=zeros(len(d))
    la=zeros(len(d))
    for k in range(len(d)):
        if isnan(az[k]): #No azimuth because I'm on the epicenter
            print 'Point on epicenter'
            lo[k]=epicenter[0]
            la[k]=epicenter[1]
        else:
            lo[k],la[k],ba=g.fwd(epicenter[0],epicenter[1],az[k],d[k]) 
    #Sort them from top right to left along dip
    zunique=unique(z)
    for k in range(len(zunique)):
        i=where(z==zunique[k])[0] #This finds all faults at a certain depth
        isort=argsort(la[i]) #This sorths them south to north
        if k==0: #First loop
            laout=la[i][isort]
            loout=lo[i][isort]
            zout=z[i][isort]
        else:
            laout=r_[laout,la[i][isort]]
            loout=r_[loout,lo[i][isort]]
            zout=r_[zout,z[i][isort]]
    #Write to file
    strike=ones(loout.shape)*strike
    dip=ones(loout.shape)*dip
    tw=ones(loout.shape)*0.5
    rise=ones(loout.shape)*rise_time
    L=ones(loout.shape)*dx_strike*1000
    W=ones(loout.shape)*dx_dip*1000
    f=open(fout,'w')
    for k in range(len(x)):   
        out='%i\t%.6f\t%.6f\t%.3f\t%.2f\t%.2f\t%.1f\t%.1f\t%.2f\t%.2f\n' % (k+1,loout[k],laout[k],zout[k],strike[k],dip[k],tw[k],rise[k],L[k],W[k])
        f.write(out)
    f.close()
    
    
def make_checkerboard(rupt,nstrike,ndip,fout,nwin):
    '''
    Make checekrboard for resolution analysis
    '''
    from numpy import genfromtxt,unique,arange,union1d,savetxt
   
    f=genfromtxt(rupt)
    u=unique(f[:,0])
    f=f[0:len(u),:]
    #Set strike-slip/dip_slip to zero
    f[:,8]=0
    f[:,9]=0
    #1 and 2
    i1=arange(0,nstrike,4)
    i2=arange(1,nstrike,4)
    i=union1d(i1,i2)
    j1=arange(21,2*nstrike,4)
    j2=arange(22,2*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 3 and 4
    i1=arange(44,3*nstrike,4)
    i2=arange(45,3*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(65,4*nstrike,4)
    j2=arange(66,4*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 5 and 6
    i1=arange(84,5*nstrike,4)
    i2=arange(85,5*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(105,6*nstrike,4)
    j2=arange(106,6*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 7 and 8
    i1=arange(128,7*nstrike,4)
    i2=arange(129,7*nstrike,4)
    i=union1d(i1,i2)
    j1=arange(149,8*nstrike,4)
    j2=arange(150,8*nstrike,4)
    j=union1d(j1,j2)
    ij=union1d(i,j)
    f[ij,9]=1
    # 9
    i1=arange(168,9*nstrike,4)
    i2=arange(169,9*nstrike,4)
    ij=union1d(i1,i2)
    f[ij,9]=1
    #Write to file
    fmt='%6i\t%.4f\t%.4f\t%8.4f\t%.2f\t%.2f\t%.2f\t%.2f\t%12.4e\t%12.4e%10.1f\t%10.1f\t%8.4f\t%.4e'
    savetxt(fout,f,fmt)
    
def model_resolution(Gfile,outdir,fault,nwindows,Ls,Lt,lambda_s,lambda_t):
    '''
    Compute model resolution matrix and output to GMT plottable file
    '''
    from numpy import load,diag,arange,zeros,genfromtxt,savetxt,c_,r_,eye
    from scipy.linalg import inv
    
    #read fault model
    lon=genfromtxt(fault,usecols=1)
    lat=genfromtxt(fault,usecols=2)
    nfaults=len(lon)
    nfaults_total=nfaults*nwindows*2
    G=load(Gfile)
    ##Tsunami weights
    #W=eye(G.shape[0])
    #W[4302:,4302:]=W[4302:,4302:]*2
    #W=W*1.1
    #G=W.dot(G)
    ##
    #Vel weights
    #W=eye(G.shape[0])*4.5
    #G=W.dot(G)
    #
    ##Combine everything
    #Gdisp=load(Gfile_disp)
    #Gvel=load(Gfile_vel)
    #W=eye(Gvel.shape[0])*4.5
    #Gvel=W.dot(Gvel)
    #Gtsun=load(Gfile_tsun)
    #W=eye(Gtsun.shape[0])
    #W[4302:,4302:]=W[4302:,4302:]*2
    #W=W*1.1
    #Gtsun=W.dot(Gtsun)
    #G=r_[Gdisp,Gvel]
    #Gdisp=Gvel=None
    LsLs=Ls.T.dot(Ls)
    #LtLt=Lt.T.dot(Lt)
    #R=(inv(G.T.dot(G)+(lambda_s**2)*LsLs+(lambda_t**2)*LtLt).dot(G.T)).dot(G)
    R=(inv(G.T.dot(G)+(lambda_s**2)*LsLs).dot(G.T)).dot(G)
    r=diag(R)
    R=None
    rout=zeros(nfaults)
    #Go one subfault at a time average ss and ds individually then average total ss and total ds
    #for k in range(nfaults):
    #    iss=arange(2*k,nfaults_total,nfaults)
    #    ids=arange(2*k+1,nfaults_total,nfaults)
    #    rss=r[iss].mean()
    #    rds=r[ids].mean()
    #    #rout[k]=max([rss,rds])
    #    rout[k]=rds
    #rout=r[arange(1,len(r),2)] #Saves ds
    rout=r[arange(0,len(r),2)] #Saves ss
    fout=Gfile.split('/')[-1]
    fout=outdir+fout.split('.')[0]+fout.split('.')[1]+'.R'
    savetxt(fout,c_[lon,lat,rout],fmt='%10.6f\t%10.6f\t%8.4f')
    
def trim_add_noise(data_path,checker_path,search_pattern):
    '''
    Trim checkerboard data and Add gaussian noise to data
    
    data_path='/Volumes/Kanagawa/Slip_Inv/tohoku_10s/data/waveforms/'
    search_pattern='checker.*disp*'
    checker_path='/Volumes/Kanagawa/Slip_Inv/tohoku_10s/output/forward_models/'    
    '''
    from numpy import var
    from numpy.random import normal
    from glob import glob
    from obspy import read
    
    checker_files=glob(checker_path+search_pattern)
    for k in range(len(checker_files)):
        ch=read(checker_files[k])
        #Find corresponding data file
        sta=checker_files[k].split('/')[-1].split('.')[1]
        vord=checker_files[k].split('/')[-1].split('.')[2]
        comp=checker_files[k].split('/')[-1].split('.')[3]
        data_file=glob(data_path+sta+'*'+vord+'*'+comp)
        st=read(data_file[0])
        ch.trim(starttime=st[0].stats.starttime,endtime=st[0].stats.endtime)
        #determine variance
        v=2e-5 #vel
        noise=normal(loc=0.0, scale=v**0.5, size=ch[0].stats.npts)
        ch[0].data=ch[0].data+noise
        ch.write(checker_files[k],format='SAC')
        
def padGFs(pad):
    '''
    Pad GFs with some extra zeros or with last value
    '''
    from glob import glob
    from obspy import read
    from numpy import ones,r_,zeros
    pad=150
    folders=glob('/Users/dmelgar/Slip_inv/Nepal_fwd/GFs/dynamic/*sub*')
    for k in range(len(folders)):
        print str(k)+' / '+str(len(folders))
        esubs=glob(folders[k]+'/*vel.e')
        nsubs=glob(folders[k]+'/*vel.n')
        zsubs=glob(folders[k]+'/*vel.z')
        for ksub in range(len(esubs)):
            e=read(esubs[ksub])
            n=read(nsubs[ksub])
            z=read(zsubs[ksub])
            #If displacement
            #e[0].data=r_[e[0].data,ones(pad)*e[0].data[-1]]
            #e.write(esubs[ksub],format='SAC')
            #
            #n[0].data=r_[n[0].data,ones(pad)*n[0].data[-1]]
            #n.write(nsubs[ksub],format='SAC')
            #
            #z[0].data=r_[z[0].data,ones(pad)*z[0].data[-1]]
            #z.write(zsubs[ksub],format='SAC')
            
            #If velocity
            e[0].data=r_[e[0].data,zeros(pad)]
            e.write(esubs[ksub],format='SAC')
            
            n[0].data=r_[n[0].data,zeros(pad)]
            n.write(nsubs[ksub],format='SAC')
            
            z[0].data=r_[z[0].data,zeros(pad)]
            z.write(zsubs[ksub],format='SAC')
            
def make_grid(lon_min,lon_max,lat_min,lat_max,delta_lon,delta_lat,out_file):
    '''
    Make a regular grid of points for GF computations
    '''
    
    from numpy import arange
    from string import rjust
    
    lon=arange(lon_min,lon_max+delta_lon,delta_lon)
    lat=arange(lat_min,lat_max+delta_lat,delta_lat)
    k=0
    f=open(out_file,'w')
    for i in range(len(lon)):
        for j in range(len(lat)):
            out='%s\t%10.4f\t%10.4f\n' %('SF'+rjust(str(k),4,'0'),lon[i],lat[j])
            f.write(out)
            k+=1
    f.close()
        
    
def usgs2fault(usgs_model,out_file):
    '''
    Convert USGS finite fault to .fault
    '''
    from numpy import genfromtxt,ones,arange,savetxt,c_
    
    lon=genfromtxt(usgs_model,usecols=1)
    lat=genfromtxt(usgs_model,usecols=0)
    z=genfromtxt(usgs_model,usecols=2)
    st=genfromtxt(usgs_model,usecols=5)
    dip=genfromtxt(usgs_model,usecols=6)
    
    no=arange(1,len(lon)+1)
    H=15e3*ones(len(lon))
    W=20e3*ones(len(lon))
    tri=0.5*ones(len(lon))
    rt=20*ones(len(lon))
    
    out=c_[no,lon,lat,z,st,dip,tri,rt,H,W]
    savetxt(out_file,out,fmt='%d\t%10.4f\t%10.4f\t%8.4f\t%6.1f\t%6.1f\t%.1f\t%.1f\t%.1f\t%.1f')
    
def usgs2rupt(usgs_model,out_file):
    '''
    Convert USGS finite fault to .fault
    '''
    from numpy import genfromtxt,ones,arange,savetxt,c_,deg2rad,cos,sin,zeros
    
    lon=genfromtxt(usgs_model,usecols=1)
    lat=genfromtxt(usgs_model,usecols=0)
    z=genfromtxt(usgs_model,usecols=2)
    st=genfromtxt(usgs_model,usecols=5)
    dip=genfromtxt(usgs_model,usecols=6)
    rake=genfromtxt(usgs_model,usecols=4)
    slip=genfromtxt(usgs_model,usecols=3)
    #Parse rake out into SS and DS
    ss=(slip/100)*cos(deg2rad(rake))
    ds=(slip/100)*sin(deg2rad(rake))
    
    no=arange(1,len(lon)+1)
    H=15e3*ones(len(lon))
    W=20e3*ones(len(lon))
    tri=0.5*ones(len(lon))
    rt=20*ones(len(lon))
    time=zeros(len(lon))
    mu=zeros(len(lon))

    out=c_[no,lon,lat,z,st,dip,tri,rt,ss,ds,H,W,time,mu]
    savetxt(out_file,out,fmt='%d\t%10.4f\t%10.4f\t%8.4f\t%6.1f\t%6.1f\t%.1f\t%.1f\t%8.4f\t%8.4f\t%.1f\t%.1f\t%d\t%d')
    
def grid2xyz(home,project_name,sta_file,out_file):
    '''
    Read forward calculated station files and make an xyz file for plotting
    '''
    
    from numpy import genfromtxt
    
    sta=genfromtxt(home+project_name+'/data/station_info/'+sta_file,usecols=0,dtype='S')
    lon=genfromtxt(home+project_name+'/data/station_info/'+sta_file,usecols=1)
    lat=genfromtxt(home+project_name+'/data/station_info/'+sta_file,usecols=2)
    f=open(out_file,'w')
    for k in range(len(sta)):
        neu=genfromtxt(home+project_name+'/output/forward_models/'+sta[k]+'.static.neu')
        n=neu[0]
        e=neu[1]
        u=neu[2]
        out='%s\t%10.4f\t%10.4f\t%10.4f\t%10.4f\t%10.4f\n' %(sta[k],lon[k],lat[k],n,e,u)
        f.write(out)
    f.close()
        
    
def static2kineamtic(rupt,epicenter,vr,fout):
    '''
    Take a static .inv or .rupt file and convert to a kinematic file given
    a rupture velocity vr
    '''
    from numpy import genfromtxt,savetxt
    from mudpy.inverse import epi2subfault
    
    #Read rupture file
    source=genfromtxt(rupt)
    #Determien distance from subfaults to epicenter
    tdelay=epi2subfault(epicenter,source,vr,0)
    source[:,12]=tdelay
    fmtout='%6i\t%.4f\t%.4f\t%8.4f\t%.2f\t%.2f\t%.2f\t%.2f\t%12.4e\t%12.4e%10.1f\t%10.1f\t%8.4f\t%.4e'
    savetxt(fout,source,fmtout,header='No,lon,lat,z(km),strike,dip,rise,dura,ss-slip(m),ds-slip(m),ss_len(m),ds_len(m),rupt_time(s),rigidity(Pa)')



def mudpy2srf(rupt,log_file,stf_dt=0.1,stf_type='dreger'):
    '''
    Convert a mudpy .rupt or .inv file to SRF version 2 format
    
    See for SRF format description here:
        https://scec.usc.edu/scecpedia/Standard_Rupture_Format
    '''
    
    from numpy import genfromtxt,where,sin,deg2rad,array,argmin,sqrt,sign,arctan2,rad2deg,arange,ones
    from pyproj import Geod
    from string import replace
    from os import path
    
    #Define paths to output files
    folder=path.dirname(rupt)
    basename=path.basename(rupt)
    basename=replace(basename,'rupt','srf')
    srf_file=folder+'/'+basename
    basename=replace(basename,'srf','src')
    src_file=folder+'/'+basename
    
    #Read mudpy file
    f=genfromtxt(rupt)
    
    
    #Calculate stuff for the header
    
    #Get coordiantes of shallowest row
    min_row=where(f[:,3]==f[:,3].min())[0]
    fmin=f[min_row,:]
    
    #Top center longitude
    elon=fmin[:,1].mean()
    
    #Top center latitude
    elat=fmin[:,2].mean()
    
    #Number of faults along strike
    Nstrike=len(fmin)
    
    #Number of faults along dip
    Ndip=len(f)/Nstrike
    
    #Subfault dimensions (in km)
    dx_strike=f[0,10]/1000.0
    dx_dip=f[0,11]/1000.0
    
    #Segment length and width
    length=Nstrike*dx_strike
    width=Ndip*dx_dip
    
    #Segment strike and dip
    strike=f[0,4]
    dip=f[0,5]
    
    #Depth to top of fault
    depth_top=fmin[0,3]-sin(deg2rad(dip))*(dx_dip/2)
    
    #Location of hypocenter from log file and magnitude
    flog=open(log_file,'r')
    while True:
        line=flog.readline()
        if 'Hypocenter (lon,lat,z[km])' in line:                
            s=replace(line.split(':')[-1],'(','')
            s=replace(s,')','')
            hypocenter=array(s.split(',')).astype('float')
        if 'Actual magnitude' in line:
            Mw=float(line.split()[-1])
        elif line=='':
            break 
    flog.close()
    
    #Down dip location with regards to top of fault
    dip_hypo_position=(hypocenter[2]-depth_top)*sin(deg2rad(dip))
    
    #Get hypocenter row of subfaults and find coordinates of middle
    hypo_row=where(f[:,3]==hypocenter[2])[0]
    hypo_center_lon=f[hypo_row,1].mean()
    hypo_center_lat=f[hypo_row,2].mean()
    #Distance from edge
    g=Geod(ellps='WGS84')
    az,baz,dist_from_center=g.inv(hypocenter[0],hypocenter[1],hypo_center_lon,hypo_center_lat)
    
    #Now decide if distance is positive or negative
    if strike>180:
        strike_rectified=strike-360
    if sign(az)==sign(strike_rectified):
        strike_hypo_position=-dist_from_center/1000
    else:
        strike_hypo_position=dist_from_center/1000
        
    #open SRF file and write header data
    fout=open(srf_file,'w')
    fout.write('2.0\n') #SRF version
    fout.write('PLANE 1\n')
    fout.write('%.6f\t%.6f\t%d\t%d\t%.4f\t%.4f\n' % (elon,elat,Nstrike,Ndip,length,width))
    fout.write('%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n' % (strike,dip,depth_top,strike_hypo_position,dip_hypo_position))
    fout.write('POINTS %d\n' % (Nstrike*Ndip))
    
    #While we're here let's write the SRC file too
    fsrc=open(src_file,'w')
    fsrc.write('MAGNITUDE = %.4f\n' % Mw)
    fsrc.write('FAULT_LENGTH = %.4f\n' % length)
    fsrc.write('DLEN = %.4f\n' % dx_strike)
    fsrc.write('FAULT_WIDTH = %.4f\n' % width)
    fsrc.write('DWID = %.4f\n' % dx_dip)
    fsrc.write('DEPTH_TO_TOP = %.4f\n' % depth_top)
    fsrc.write('STRIKE = %.4f\n' % strike)
    fsrc.write('RAKE = 9999\n')
    fsrc.write('DIP = %.4f\n' % dip)
    fsrc.write('LAT_TOP_CENTER = %.4f\n' % elat)
    fsrc.write('LON_TOP_CENTER = %.4f\n' % elon)
    fsrc.write('HYPO_ALONG_STK = %.4f\n' % strike_hypo_position)
    fsrc.write('HYPO_DOWN_DIP = %.4f\n' % dip_hypo_position)
    fsrc.write('DT = 0.01\n')
    fsrc.write('SEED = 1')
    fsrc.close()
    
    #And that was jsut the headers, now let's move on to getting the subfault source time functions
    # Note mudpy works in mks SRF is cgs so must convert accordingly
    for kfault in range(len(f)):
        #Get values for "Headers" for this subfault
        lon=f[kfault,1]
        lat=f[kfault,2]
        depth=f[kfault,3]
        strike=f[kfault,4]
        dip=f[kfault,5]
        area=f[kfault,10]*f[kfault,11]*100**2
        tinit=f[kfault,12]
        vs=-1 #Default value for not known
        density=-1 #default value for not known
        rake=rad2deg(arctan2(f[kfault,9],f[kfault,8]))
        slip=sqrt(f[kfault,8]**2+f[kfault,9]**2)*100
        
        #Now get source time function
        rise_time=f[kfault,7]
        total_time=rise_time*1.5
        #If subfault has zero rise time make it have tiny sli rate
        if rise_time==0:
            tstf=arange(3)*stf_dt
            stf=1e-6*ones(3)
        else:
            tstf,stf=build_source_time_function(rise_time,stf_dt,total_time,stf_type=stf_type,zeta=0.2,scale=True)
            #Scale stf so integral matches total slip
            stf_adjust_factor=slip/stf_dt
            stf=stf*stf_adjust_factor #now tf is in cm/sec       
        
        #How mant STF points?
        NTstf=len(stf)
        
        #Write the subfault headers
        fout.write('%.6f\t%.6f\t%.5e\t%.2f\t%.2f\t%.5e\t%.4e\t%.4e\t%.4e\t%.4e\n' % (lon,lat,depth,strike,dip,area,tinit,stf_dt,vs,density))
        fout.write('%.2f\t%.4f\t%d\t0\t0\t0\t0\n' % (rake,slip,NTstf))
        
        #Write stf 6 values per line
        for kstf in range(NTstf):
            if kstf==0:
                white_space='\t'
            elif (kstf+1) % 6 == 0:
                white_space='\n'
            elif (kstf+1)==NTstf:
                white_space='\n'
            else:
                white_space='\t'
            fout.write('%.6f%s' % (stf[kstf],white_space))

    
    # And done
    fout.close()



def convolution_matrix(h):
    '''
    Return the TOeplitz-like convolution matrix for a time series
    '''
    
    from numpy import zeros,r_
    from scipy.linalg import toeplitz
    
    
    padding = zeros(h.shape[0] - 2, h.dtype)
    first_col = r_[h, padding]
    first_row = r_[h[0], padding]
    Htemp = toeplitz(first_col, first_row)
    Hfinal= Htemp[0:len(h),:]
    return Hfinal
    
    
def build_source_time_function(rise_time,dt,total_time,stf_type='triangle',zeta=0.2,dreger_falloff_rate=4,scale=True):
    '''
    Compute source time function for a given rise time, right now it assumes 1m of slip
    and a triangle STF
    '''
    from numpy import zeros,arange,where,pi,cos,sin,isnan,exp
    from scipy.integrate import trapz
    
    rise_time=float(rise_time)
    #Initialize outputs
    t=arange(0,total_time+dt,dt)
    Mdot=zeros(t.shape)
    if stf_type=='triangle':
        #Triangle gradient
        m=1/(rise_time**2)
        #Upwards intercept
        b1=0
        #Downwards intercept
        b2=m*(rise_time)
        #Assign moment rate
        i=where(t<=rise_time/2)[0]
        Mdot[i]=m*t[i]+b1
        i=where(t>rise_time/2)[0]
        Mdot[i]=-m*t[i]+b2 
        i=where(t>rise_time)[0]
        Mdot[i]=0
    elif stf_type=='cosine':   #From Liu et al. (2006) BSSA, eq 7a,7b
        tau1=0.13*rise_time
        tau2=rise_time-tau1
        Cn=pi/(1.4*pi*tau1+1.2*tau1+0.3*pi*tau2)
        #Build in pieces
        i1=where(t<tau1)[0]
        i2=where((t>=tau1) & (t<2*tau1))[0]
        i3=where((t>=2*tau1) & (t<rise_time))[0]
        Mdot[i1]=Cn*(0.7-0.7*cos(t[i1]*pi/tau1)+0.6*sin(0.5*pi*t[i1]/tau1))
        Mdot[i2]=Cn*(1.0-0.7*cos(t[i2]*pi/tau1)+0.3*cos(pi*(t[i2]-tau1)/tau2))
        Mdot[i3]=Cn*(0.3+0.3*cos(pi*(t[i3]-tau1)/tau2))
    elif stf_type=='dreger':
        tau=rise_time/dreger_falloff_rate
        Mdot=(t**zeta)*exp(-t/tau)
    else:
        print 'ERROR: unrecognized STF type '+stf_type
        return
    #Area of STF must be equal to dt
    if scale==True:
        area=trapz(Mdot,t)
        Mdot=Mdot*(dt/area)
    #Check for errors
    if isnan(Mdot[0])==True:
        print 'ERROR: woops, STF has nan values!'
        return
    return t,Mdot
    
    
def read_fakequakes_hypo_time(home,project_name,rupture_name):
    '''
    Read a fakequkaes log file and extrat hypocentral time
    '''
    
    from obspy.core import UTCDateTime
    from string import replace
    from numpy import array
    
    rupture=rupture_name.split('.')[0]+'.'+rupture_name.split('.')[1]
    log_file=home+project_name+'/output/ruptures/'+rupture+'.log'
    f=open(log_file,'r')
    while True:
        line=f.readline()
        if 'Hypocenter (lon,lat,z[km])' in line:
            s=replace(line.split(':')[-1],'(','')
            s=replace(s,')','')
            epicenter=array(s.split(',')).astype('float')
        if 'Hypocenter time' in line:
            time_epi=line.split(' ')[-1]
            time_epi=UTCDateTime(time_epi)
            break
        if line=='':
            print 'ERROR: No hypocetral time in log file'
            time_epi=''
            break
    return epicenter,time_epi
    
    