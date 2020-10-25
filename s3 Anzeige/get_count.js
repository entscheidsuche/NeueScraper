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