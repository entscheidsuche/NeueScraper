<?php
	header('Content-Type: application/json');

	// Liest das Objekt "signaturen" aus einer Job-Datei, ohne die ganze Datei zu
	// dekodieren (Job-Dateien grosser Spider haben >50 MB). Gelesen wird
	// blockweise von vorne, bis "signaturen" gefunden und das Objekt vollstaendig
	// ist; so wird bei Dateien mit "signaturen" am Anfang nur der erste Block gelesen.
	function lese_signaturen($pfad){
		$fh=fopen($pfad,'rb');
		if($fh===false){
			return array();
		}
		$puffer='';
		$start=-1;
		while(true){
			$block=fread($fh,65536);
			$ende=($block===false || $block==='');
			if(!$ende){
				$puffer.=$block;
			}
			if($start<0){
				if(preg_match('/"signaturen"\s*:\s*\{/',$puffer,$m,PREG_OFFSET_CAPTURE)){
					$start=$m[0][1]+strlen($m[0][0])-1;
					$puffer=substr($puffer,$start);
					$start=0;
				}
				else {
					// Rest behalten, falls der Suchbegriff ueber die Blockgrenze reicht
					$puffer=substr($puffer,-64);
				}
			}
			if($start>=0){
				$tiefe=0;
				$in_string=false;
				$len=strlen($puffer);
				for($i=0;$i<$len;$i++){
					$c=$puffer[$i];
					if($in_string){
						if($c==='\\'){
							$i++;
						}
						elseif($c==='"'){
							$in_string=false;
						}
					}
					elseif($c==='"'){
						$in_string=true;
					}
					elseif($c==='{'){
						$tiefe++;
					}
					elseif($c==='}'){
						$tiefe--;
						if($tiefe===0){
							fclose($fh);
							$sig=json_decode(substr($puffer,0,$i+1),true);
							return is_array($sig) ? $sig : array();
						}
					}
				}
			}
			if($ende){
				fclose($fh);
				return array();
			}
		}
	}
	$facetten=file_get_contents('Facetten_alle.json');
	$facettendata=json_decode($facetten,true);
	$spiderliste=array();
	$signaturliste=array();
	foreach ($facettendata as $kanton => $kantonsdaten){
		foreach ($kantonsdaten['gerichte'] as $gericht => $gerichtsdaten){
			foreach ($gerichtsdaten['kammern'] as $kammer => $kammerdaten){
				$spider = $kammerdaten['spider'];
				if (! in_array($spider, $spiderliste)){
					$spiderliste[] = $spider;
				}
			}
		}
	}
	
	foreach ($spiderliste as $spider){
		$liste=glob('Jobs/'.$spider.'/Job_*.json');
		// print("\nSpider: " . $spider .":\n");
		if(count($liste)>0){
			rsort($liste);
			$data=array('signaturen' => lese_signaturen($liste[0]));
			foreach ($data['signaturen'] as $signatur => $signaturdaten){
				$signaturliste[]=$signatur;
				// print("Signatur " . $signatur . " hinzugefügt.\n");
			}
		}
	}
		
	foreach ($facettendata as $kanton => $kantonsdaten){
		foreach ($kantonsdaten['gerichte'] as $gericht => $gerichtsdaten){
			$leerekammern=array();
			foreach ($gerichtsdaten['kammern'] as $kammer => $kammerdaten){
				$pos=array_search($kammer, $signaturliste);
				if ($pos===false){
					$leerekammern[]=$kammer;
				}
				else {
					unset($signaturliste[$pos]);
				}
			}
			foreach ($leerekammern as $leer){
				unset($facettendata[$kanton]['gerichte'][$gericht]['kammern'][$leer]);
			}
		}
	}
	
	foreach ($signaturliste as $kammer){
		// print("Kammer: " . $kammer . "\n");
		$teile=explode("_",$kammer);
		$kanton=$teile[0];
		// print("Kanton: " . $kanton . "\n");
		$gericht=$teile[0] . "_" . $teile[1];
		// print("Gericht: " . $gericht . "\n");
		if (!(array_key_exists($kanton,$facettendata))){
			$facettendata[$kanton]=array('de' => $kanton, 'fr' => $kanton, 'it' => $kanton, 'gerichte' => array());
		}
		if (!(array_key_exists($gericht,$facettendata[$kanton]['gerichte']))){
			$facettendata[$kanton]['gerichte'][$gericht]=array('de' => $gericht, 'fr' => $gericht, 'it' => $gericht, 'kammern' => array());
		}
		$facettendata[$kanton]['gerichte'][$gericht]['kammern'][$kammer]=array('spider' => "unbekannt", 'de' => $kammer, 'fr' => $kammer, 'it' => $kammer);
	}
	

	print(json_encode($facettendata));
?>
