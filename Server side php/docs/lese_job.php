<?php
	// Liefert den neuesten Job_*.json eines Spiders aus dem Jobs-Verzeichnis.
	// Filter auf den Filename-Prefix 'Job_' (statt aller *.json), damit
	// abweichend benannte Dateien (z.B. 'alt_Job_*.json' aus manuellen
	// Reparaturen, '*.tmp.*' aus atomaren Schreibvorgängen, Failed_Job_*.json
	// usw.) nicht versehentlich als "neuester Lauf" interpretiert werden.
	$spider=$_REQUEST['spider'];
	header('Content-Type: application/json');
	if(strpos($spider, '.') == false){
		$liste=glob('Jobs/'.$spider.'/Job_*.json');
		if(count($liste)==0){
			$data = ['spider' => $spider, 'job' => 'nojob'];
			print(json_encode($data));
		}
		else {
			rsort($liste);
			$content=file_get_contents ( $liste[0]);
			print($content);
		}
	}
?>
