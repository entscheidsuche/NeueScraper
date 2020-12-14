
function toggle(spider){
	icon_element=document.getElementById("Icon_"+spider);
	body_element=document.getElementById("Body_"+spider);
	src_len=icon_element.src.length
	if(icon_element.src.substring(src_len-11,src_len)=="Icon_zu.png"){
		icon_element.src="/Icon_auf.png";
		body_element.style="";
	}
	else{
		icon_element.src="/Icon_zu.png";
		body_element.style="display:none";
	}

}
  

// Alte Funktion für S3

function get_count(spider, eintrag){
	var count={xml:0, html:0, pdf:0}
	get_count_rec(spider, eintrag, count);
  }

  function get_count_rec(spider, eintrag, count, marker=""){
  	var url='http://entscheidsuche.ch.s3-eu-west-3.amazonaws.com/?delimiter=/&prefix=scraper/'+spider+'/'+eintrag;
  	if(!!marker){
  		url += '&marker='+marker;
  	}
  	var xhttp = new XMLHttpRequest();
		xhttp.onreadystatechange = function(_spider=spider, _eintrag=eintrag) {
    		if (this.readyState == 4 && this.status == 200) {
    	   		// action to be performed when the document is ready:
	    	   var xmlDoc = xhttp.responseXML;
	    	   var dateien=xmlDoc.getElementsByTagName('Key');
	    	   for (i=0;i<dateien.length;i++){
	    	   		var dateiname=dateien[i].innerHTML;
	    	   		var splitname=dateiname.split(".");
	    	   		if(splitname.length>1){
	    	   			var endung=splitname[splitname.length-1];
	    	   			if (endung in count) count[endung]++;
	    	   			else count[endung]=1;
	    	   		}
	    	   }
	    	   var next_marker=xmlDoc.getElementsByTagName('NextMarker');
	    	   if(next_marker.length>0) get_count_rec(spider, eintrag, count, next_marker[0].innerHTML);
	    	   else{
					document.getElementById(eintrag).innerHTML=count['xml'].toString();
					var total_e=document.getElementById("total");
					total_e.innerHTML=(count['xml']+parseInt(total_e.innerHTML,10)).toString();
	    	   }
    		}
		};
	xhttp.open("GET", url, true);
	xhttp.send();
  	
  }
  
  function set_count(eintrag, gesamtzahl, neu, changed, entfernt){
  	// alert(eintrag+" gesamt: "+gesamtzahl.toString()+", neu: "+neu.toString()+", geändert: "+changed.toString()+", entfernt: "+entfernt.toString());
	var gesamtzahl_e=document.getElementById("total");
	gesamtzahl_e.innerHTML=(gesamtzahl+parseInt(gesamtzahl_e.innerHTML,10)).toString();
	var neu_e=document.getElementById("neu");
	neu_e.innerHTML=(neu+parseInt(neu_e.innerHTML,10)).toString();
	var changed_e=document.getElementById("changed");
	changed_e.innerHTML=(changed+parseInt(changed_e.innerHTML,10)).toString();
	var entfernt_e=document.getElementById("entfernt");
	entfernt_e.innerHTML=(entfernt+parseInt(entfernt_e.innerHTML,10)).toString();
  }
  
  function set_info(eintrag, text){
	var element=document.getElementById(eintrag);
	if (element!=null) element.innerHTML=text;  	
  }

  function setze_info_string(dict, eintrag, text, jobtyp){
  	var subtext="";
  	var gesamt=0;
  	var neu=0;
  	var changed=0;
  	var entfernt=0;
  	if('gesamt' in dict){
		var gesamtzahl=dict.gesamt;
		if("aktuell_neu" in dict){
			subtext="neu: "+dict['aktuell_neu'];
			neu=dict['aktuell_neu'];
		}
		if("aktuell_aktualisiert" in dict){
			if (subtext!="") subtext+=", ";
			subtext+="aktualisiert: "+dict['aktuell_aktualisiert'];
			changed=dict['aktuell_aktualisiert']
		}
		if("aktuell_entfernt" in dict){
			if (subtext!="") subtext+=", ";
			subtext+="entfernt: "+dict['aktuell_entfernt'];
			entfernt=dict['aktuell_entfernt'];
		}
		if(subtext==""){
			subtext="keine aktuelle Änderung";
		}
		if (subtext!="") subtext="<br><small>"+subtext+"</small>";
		set_info(eintrag, dict.gesamt+" "+text+subtext);
		if (eintrag.substring(3).includes("_")) set_count(eintrag, gesamtzahl, neu, changed, entfernt);
  	}
  }


  function process(data,spider){
  	var text="<small>"
  	jobtyp="update"
  	if ("jobtyp" in data) jobtyp=data.jobtyp
  	if (jobtyp=="komplett") text+="Komplett gelesen am "
  	else text+="Update am "
  	text += data.time + " (UTC)</small>";
	if ('signaturen' in data && 'gesamt' in data && 'gesamt' in data.gesamt){
		setze_info_string(data.gesamt,spider,text,jobtyp);
		for (s in data.signaturen){
			setze_info_string(data.signaturen[s],s,text,jobtyp);
		}
	}
  }
  
 
  function get_count_json(spider){
  		// Erst einmal die Jobliste aus S3 holen
	  	var url='http://entscheidsuche.ch.s3.amazonaws.com/?list-type=2&prefix=scraper%2F'+spider+'%2FIndex_';
  		var xhttp = new XMLHttpRequest();
  			xhttp.onreadystatechange = function(_spider=spider) {
    			if (this.readyState == 4 && this.status == 200) {
    	   			// action to be performed when the document is ready:
	    	   		var xmlDoc = xhttp.responseXML;
	    	   		var dateien=xmlDoc.getElementsByTagName('Key');
	    	   		if (dateien.length>0){
	 	   	   			var runs=[];
		    			for (i=0;i<dateien.length;i++){
	    					runs.push(dateien[i].innerHTML);
	    				}
	    				runs.sort();
	    				// Nun die neueste Job-Datei verarbeiten
	    				var filename=runs[runs.length-1];
	    				fetch('http://entscheidsuche.ch.s3.amazonaws.com/'+filename)
	    					.then( response => response.json())
	    					.then( data => process(data,spider));
	    			}
    	   		}
    	   	};
   		xhttp.open("GET", url, true);
		xhttp.send();
  	}

