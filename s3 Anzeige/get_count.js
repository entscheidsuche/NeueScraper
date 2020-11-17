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
  
  function set_count(eintrag, zahl){
	var total_e=document.getElementById("total");
	total_e.innerHTML=(zahl+parseInt(total_e.innerHTML,10)).toString();
  }
  
  function set_info(eintrag, text){
	var element=document.getElementById(eintrag);
	if (element!=null) element.innerHTML=text;  	
  }

  function setze_info_string(dict, eintrag, text, jobtyp){
  	var subtext="";
  	if('gesamt' in dict){
		var identisch=0;
		if("vorher identisch" in dict) identisch+=dict["vorher identisch"];
		if("aktuell identisch" in dict) identisch+=dict["aktuell identisch"];
		if(dict.gesamt==identisch){
			subtext="keine Änderung";
		}
		else{
			if("aktuell neu" in dict) subtext="neu: "+dict['aktuell neu'];
			if("aktuell aktualisiert" in dict){
				if (subtext!="") subtext+=", ";
				subtext+="aktualisiert: "+dict['aktuell aktualisiert'];
			}
			if("aktuell entfernt" in dict){
				if (subtext!="") subtext+=", ";
				subtext+="entfernt: "+dict['aktuell entfernt'];
			}
		}
		if (subtext!="") subtext="<br><small>"+subtext+"</small>";
		set_info(eintrag, dict.gesamt+" "+text+subtext);
  	}
  }


  function process(data,spider){
  	var text="<small>"
  	jobtyp="update"
  	if ("jobtyp" in data) jobtyp=data.jobtyp
  	if (jobtyp=="komplett") text+="Komplett gelesen am "
  	else text+="Update am "
  	text += data.time + "</small>";
	if ('signaturen' in data && 'gesamt' in data && 'gesamt' in data.gesamt){
		set_count(spider,parseInt(data.gesamt.gesamt,10));
		setze_info_string(data.gesamt, spider,text,jobtyp);
		for (s in data.signaturen){
			setze_info_string(data.signaturen[s],s,text,jobtyp);
		}
	}
  }
  
 
  function get_count_json(spider){
	  	var url='http://entscheidsuche.ch.s3.amazonaws.com/?list-type=2&prefix=scraper%2F'+spider+'%2FJob_';
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
  
  
