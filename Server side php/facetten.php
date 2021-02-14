<?php
	header('Content-Type: application/json');
	$facetten=file_get_contents('Facetten_alle.json');
	$facettendata=json_decode($facetten,true);
	$spiderliste=list();
	$signaturliste=list();
	foreach ($facettendata as $kanton => $kantonsdaten){
		foreach ($kantonsdaten['gerichte'] as $gericht => $gerichtsdaten){
			foreach ($gerichtsdaten['kammern'] as $kammer => $kammerdaten){
				$spiderliste[] = $kammerdaten['spider'];
			}
		}
	}
	
	foreach ($spiderliste as $spider){
		$liste=glob('Jobs/'.$spider.'/*');
		if(count($liste)>0){
			rsort($liste);
			$content=file_get_contents ( $liste[0]);
			$data=json_decode($content,true);
			foreach ($data['signaturen'] as $signatur){
				$signaturliste[]=$signatur
			}
		}
	}
		
	foreach ($facettendata as $kanton => $kantonsdaten){
		foreach ($kantonsdaten['gerichte'] as $gericht => $gerichtsdaten){
			$leerekammern=list();
			foreach ($gerichtsdaten['kammern'] as $kammer){
				if (not(in_array($kammer,$signaturliste)){
					$leerekammern[]=$kammer
				}
			}
			foreach ($leerekammern as $leer){
				unset($facettendata[$kanton][$gericht][$leer]
			}
		}
	}

	print(json_encode($facettendata));
?>
