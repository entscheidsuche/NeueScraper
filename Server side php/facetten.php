<?php
	header('Content-Type: application/json');
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
		$liste=glob('Index/'.$spider.'/*');
		// print("\nSpider: " . $spider .":\n");
		if(count($liste)>0){
			rsort($liste);
			$content=file_get_contents ( $liste[0]);
			$data=json_decode($content,true);
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
